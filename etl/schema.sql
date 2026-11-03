-- Schema do banco da Empório da Música (ver docs/decisoes.md, D09).
--
--   bronze  raw_*        cópia fiel dos CSVs (criada pelo pipeline, tudo TEXT)
--   silver  tabelas      tipadas, com PK/FK/CHECK e colunas de flag de qualidade (dq_*)
--   gold    vw_*         visões de negócio consumidas pelas tools do agente
--
-- O banco é reconstruído do zero a cada execução (full refresh).

PRAGMA foreign_keys = ON;

-- ============================================================================
-- SILVER
-- ============================================================================

CREATE TABLE categories (
    category_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    description   TEXT
);

CREATE TABLE products (
    product_id      INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    name_search     TEXT    NOT NULL,          -- minúsculas e sem acento, para busca
    category_id     INTEGER NOT NULL REFERENCES categories (category_id),
    description     TEXT,
    price_brl       REAL    NOT NULL CHECK (price_brl > 0),
    stock_quantity  INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status          TEXT    NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    specs           TEXT    NOT NULL CHECK (json_valid(specs)),
    created_at      TEXT    NOT NULL,          -- data ISO (AAAA-MM-DD)
    disponibilidade TEXT    NOT NULL CHECK (disponibilidade IN ('disponivel', 'sem_estoque', 'descontinuado', 'em_breve')),
    vendavel        INTEGER NOT NULL CHECK (vendavel IN (0, 1))   -- S04: status prevalece sobre estoque
);

CREATE TABLE promotions (
    promotion_id      INTEGER PRIMARY KEY,
    product_id        INTEGER NOT NULL REFERENCES products (product_id),
    discount_percent  REAL    NOT NULL CHECK (discount_percent > 0 AND discount_percent < 100),
    description       TEXT,
    is_active         INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    dq_duplicada      INTEGER NOT NULL CHECK (dq_duplicada IN (0, 1)),       -- produto tem mais de uma promoção
    dq_conflito_ativo INTEGER NOT NULL CHECK (dq_conflito_ativo IN (0, 1))   -- S06: mais de uma ativa, nenhuma vale
);

-- Preço vigente por produto, calculado em Python com src/agente/regras.py
-- (fonte única das regras de preço, PIX e conflito de promoções).
CREATE TABLE product_prices (
    product_id            INTEGER PRIMARY KEY REFERENCES products (product_id),
    preco_tabela          REAL    NOT NULL,
    promotion_id          INTEGER REFERENCES promotions (promotion_id),
    promocao_descricao    TEXT,
    desconto_percentual   REAL,
    preco_final           REAL    NOT NULL,
    preco_pix             REAL    NOT NULL,
    em_promocao           INTEGER NOT NULL CHECK (em_promocao IN (0, 1)),
    max_parcelas          INTEGER NOT NULL,
    valor_parcela_maxima  REAL    NOT NULL
);

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    name_norm     TEXT NOT NULL,   -- minúsculas, sem acento: verificação de identidade (S05)
    phone         TEXT NOT NULL,
    phone_digits  TEXT NOT NULL,   -- só dígitos: verificação de identidade (S05)
    email         TEXT NOT NULL,
    email_norm    TEXT NOT NULL,
    city          TEXT
);

CREATE TABLE orders (
    order_id                  INTEGER PRIMARY KEY,
    customer_id               INTEGER NOT NULL REFERENCES customers (customer_id),
    order_date                TEXT    NOT NULL,
    status                    TEXT    NOT NULL CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total_brl                 REAL    NOT NULL CHECK (total_brl > 0),   -- valor cobrado (original, nunca alterado)
    payment_method_raw        TEXT    NOT NULL,
    forma_pagamento           TEXT    NOT NULL CHECK (forma_pagamento IN ('pix', 'debit', 'credit', 'boleto')),
    parcelas                  INTEGER NOT NULL CHECK (parcelas BETWEEN 1 AND 12),
    tracking_code             TEXT,
    estimated_delivery        TEXT,
    notes                     TEXT,
    itens_total               REAL    NOT NULL,   -- soma dos itens a preço de tabela ATUAL
    dq_total_divergente       INTEGER NOT NULL CHECK (dq_total_divergente IN (0, 1)),
    dq_parcela_abaixo_minimo  INTEGER NOT NULL CHECK (dq_parcela_abaixo_minimo IN (0, 1))
);

CREATE TABLE order_items (
    order_item_id            INTEGER PRIMARY KEY,
    order_id                 INTEGER NOT NULL REFERENCES orders (order_id),
    product_id               INTEGER NOT NULL REFERENCES products (product_id),
    quantity                 INTEGER NOT NULL CHECK (quantity > 0),
    dq_produto_fora_de_comercializacao  INTEGER NOT NULL CHECK (dq_produto_fora_de_comercializacao IN (0, 1))
);

-- Rótulos legíveis, gerados a partir de src/agente/regras.py
CREATE TABLE ref_status_pedido (
    status  TEXT PRIMARY KEY,
    rotulo  TEXT NOT NULL
);

CREATE TABLE ref_forma_pagamento (
    forma   TEXT PRIMARY KEY,
    rotulo  TEXT NOT NULL
);

CREATE TABLE ref_disponibilidade (
    disponibilidade  TEXT PRIMARY KEY,
    rotulo           TEXT NOT NULL
);

-- ============================================================================
-- METADADOS E QUALIDADE
-- ============================================================================

CREATE TABLE etl_metadata (
    chave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

CREATE TABLE dq_results (
    check_id    TEXT PRIMARY KEY,
    severidade  TEXT    NOT NULL CHECK (severidade IN ('erro', 'alerta')),
    resultado   TEXT    NOT NULL CHECK (resultado IN ('ok', 'falhou')),
    tabela      TEXT    NOT NULL,
    descricao   TEXT    NOT NULL,
    quantidade  INTEGER NOT NULL,
    registros   TEXT    NOT NULL,   -- JSON com os registros afetados
    tratamento  TEXT    NOT NULL    -- o que o pipeline/agente faz com o problema
);

-- ============================================================================
-- GOLD
-- ============================================================================

-- Catálogo pronto para atendimento: preço vigente, PIX, parcelamento e disponibilidade.
CREATE VIEW vw_catalogo AS
SELECT
    p.product_id,
    p.name,
    p.name_search,
    c.name                  AS categoria,
    p.description,
    p.specs,
    p.status,
    p.disponibilidade,
    d.rotulo                AS disponibilidade_rotulo,
    p.vendavel,
    p.stock_quantity,
    pp.preco_tabela,
    pp.em_promocao,
    pp.promocao_descricao,
    pp.desconto_percentual,
    pp.preco_final,
    pp.preco_pix,
    pp.max_parcelas,
    pp.valor_parcela_maxima
FROM products p
JOIN categories c          ON c.category_id = p.category_id
JOIN product_prices pp     ON pp.product_id = p.product_id
JOIN ref_disponibilidade d ON d.disponibilidade = p.disponibilidade;

-- Pedidos com itens agregados. Não expõe dados pessoais do cliente: a
-- verificação de identidade é feita pela tool antes de consultar esta view.
CREATE VIEW vw_pedidos AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_date,
    o.status,
    s.rotulo                AS status_rotulo,
    o.total_brl,
    o.forma_pagamento,
    f.rotulo                AS forma_pagamento_rotulo,
    o.parcelas,
    o.tracking_code,
    o.estimated_delivery,
    o.notes,
    (
        SELECT json_group_array(json_object(
                   'product_id', p.product_id,
                   'nome',       p.name,
                   'quantidade', oi.quantity))
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = o.order_id
    )                       AS itens
FROM orders o
JOIN ref_status_pedido s   ON s.status = o.status
JOIN ref_forma_pagamento f ON f.forma = o.forma_pagamento;
