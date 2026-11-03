"""Estilo visual da UI (identidade inspirada na Artefact: azul-marinho, magenta e
roxo, IBM Plex Sans, botões em pílula).

O magenta da marca (#FF0066) tem contraste 3,9:1 com texto branco, abaixo do
mínimo de acessibilidade (4,5:1). Onde há texto sobre magenta, usa-se #E0005A
(4,9:1); o #FF0066 puro fica para elementos sem texto.
"""

AZUL = "#0D1634"
MAGENTA = "#E0005A"
MAGENTA_VIVO = "#FF0066"
ROXO = "#7B35D6"
ROXO_CLARO = "#F3ECFF"
CINZA_TEXTO = "#5A6380"
BORDA = "#E2E5EE"
VERDE = "#1F7A3A"
VERMELHO = "#B42318"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* Fonte da marca em todo texto; os ícones do Streamlit usam a própria fonte de símbolos */
[data-testid="stApp"] *:not([data-testid="stIconMaterial"]):not(.em-mono):not(code):not(pre) {{
  font-family: 'IBM Plex Sans', Arial, sans-serif;
}}

/* Sidebar azul-marinho */
section[data-testid="stSidebar"] {{ background: {AZUL}; }}
section[data-testid="stSidebar"] * {{ color: #FFFFFF; }}
section[data-testid="stSidebar"] .em-subtitulo,
section[data-testid="stSidebar"] .em-rotulo,
section[data-testid="stSidebar"] .em-rodape {{ color: #B9C0D6; }}
section[data-testid="stSidebar"] .stButton button {{
  width: 100%; justify-content: flex-start; text-align: left; min-height: 44px;
  background: transparent; border: 1px solid rgba(255,255,255,0.28); border-radius: 22px;
}}
section[data-testid="stSidebar"] .stButton button:hover {{ border-color: #FF4D8F; background: rgba(255,0,102,0.16); }}
section[data-testid="stSidebar"] .stButton button[kind="primary"] {{
  width: auto; justify-content: center; background: {MAGENTA}; border: none; border-radius: 40px; padding: 0 24px;
}}

/* Botões e campo de mensagem em pílula */
.stButton button {{ border-radius: 40px; }}
[data-testid="stChatInput"] > div {{ border-radius: 40px; }}

/* Mensagem do cliente em magenta */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  background: {MAGENTA}; border-radius: 20px 20px 4px 20px; margin-left: 15%;
}}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {{ color: #FFFFFF; }}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageAvatarUser"] {{ display: none; }}

/* Cartões */
.em-card {{ background: #FFFFFF; border: 1px solid {BORDA}; border-radius: 16px; padding: 18px 20px; margin: 6px 0 10px; color: {AZUL}; }}
.em-card-escuro {{ background: {AZUL}; border: none; color: #FFFFFF; }}
.em-linha {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }}
.em-titulo {{ font-size: 18px; font-weight: 600; }}
.em-sub {{ font-size: 14px; color: {CINZA_TEXTO}; }}
.em-preco {{ font-size: 30px; font-weight: 300; margin: 6px 0; }}
.em-riscado {{ font-size: 16px; color: {CINZA_TEXTO}; text-decoration: line-through; margin-right: 10px; }}
.em-pilula {{ display: inline-block; padding: 4px 12px; border-radius: 40px; font-size: 14px; font-weight: 500; margin: 2px 6px 2px 0; }}
.em-ok {{ background: #E7F4EC; color: #1F5F33; }}
.em-cinza {{ background: #ECEEF4; color: #3A4260; }}
.em-promo {{ background: #FFE5F0; color: #A3003F; font-weight: 600; }}
.em-roxo {{ background: {ROXO_CLARO}; color: #5B21B6; }}
.em-info {{ background: #F5F6FA; color: {AZUL}; font-weight: 400; }}
.em-grade {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 24px; font-size: 15px; margin-top: 10px; }}
.em-grade span.em-sub {{ display: block; }}
.em-alts {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 8px; }}
.em-alt {{ border: 1px solid {BORDA}; border-radius: 12px; padding: 10px 12px; font-size: 14px; line-height: 1.4; }}
.em-prazos {{ border-top: 1px solid #EEF0F6; margin-top: 12px; padding-top: 10px; font-size: 15px; }}
.em-prazos div {{ display: flex; justify-content: space-between; gap: 12px; margin: 4px 0; }}
.em-encerrado {{ color: {VERMELHO}; font-weight: 600; }}
.em-vigente {{ color: {VERDE}; font-weight: 600; }}
.em-alerta {{ background: #FFE5F0; color: #8F0039; border-radius: 12px; padding: 10px 14px; margin-top: 10px; font-size: 15px; }}
.em-mono {{ font-family: 'IBM Plex Mono', monospace; }}
.em-rotulo-fontes {{ font-size: 12px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {CINZA_TEXTO}; margin-top: 14px; }}

/* Plano (checklist) */
.em-plano {{ background: #FFFFFF; border: 1px solid {BORDA}; border-radius: 16px; padding: 16px 18px; margin-bottom: 10px; }}
.em-plano-topo {{ font-size: 12px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {ROXO}; }}
.em-plano-objetivo {{ font-size: 15px; margin: 6px 0 10px; }}
.em-barra {{ height: 4px; border-radius: 4px; background: #EEF0F6; overflow: hidden; margin-bottom: 10px; }}
.em-barra > div {{ height: 4px; background: {MAGENTA_VIVO}; transition: width 0.4s ease; }}
.em-passo {{ display: flex; align-items: center; gap: 10px; font-size: 15px; margin: 6px 0; }}
.em-passo.pendente {{ color: {CINZA_TEXTO}; }}
.em-marca {{ flex: 0 0 22px; height: 22px; box-sizing: border-box; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }}
.em-marca.feito {{ background: {ROXO}; color: #FFFFFF; font-size: 13px; }}
.em-marca.pendente {{ border: 2px solid #C9CEDC; }}
.em-marca.rodando {{ border: 3px solid {ROXO_CLARO}; border-top-color: {ROXO}; animation: em-giro 0.8s linear infinite; }}
.em-andamento {{ font-size: 13px; color: {ROXO}; }}
.em-faltando {{ font-size: 14px; color: {CINZA_TEXTO}; margin-top: 8px; }}
.em-status {{ font-size: 14px; color: {CINZA_TEXTO}; display: flex; align-items: center; gap: 8px; }}
@keyframes em-giro {{ to {{ transform: rotate(360deg); }} }}
</style>
"""
