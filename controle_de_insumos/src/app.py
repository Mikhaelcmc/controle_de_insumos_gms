import streamlit as st
from supabase import create_client
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Logística GMS", layout="wide", page_icon="📦")

# --- CSS PERSONALIZADO (CORES DA GMS) ---
st.markdown("""
    <style>
    /* Centralizar container de login */
    .stTextInput > div > div > input {
        border-radius: 8px;
    }
    /* Estilo dos Botões */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #004684; /* Azul GMS */
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #002d55;
        color: white;
    }
    /* Métrica de Estoque */
    [data-testid="stMetricValue"] {
        font-size: 32px;
        color: #004684;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÃO SUPABASE ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL, KEY)

# --- LISTAS FIXAS ---
VDS = ["23924-HUB", "14523-ITABATÃ", "19081-ITAMARAJU", "13483-PORTO SEGURO", "18481-TEIXEIRA", "13481-EUNÁPOLIS", "23332-BARRA"]
PRODUTOS = ["1 - Caixas Omni PP", "2 - Caixas Omni P", "3 - Caixas Omni M", "4 - Caixas entregas P", "5 - Caixas entregas M", "6 - Etiquetas entrega", "7 - Ribbon", "8 - Fita gomada", "9 - Fita adesiva", "10 - SACOLA PP BOTI INST 2025", "11 - SACOLA P BOTI INST 2025", "12 - SACOLA M BOTI INST 2025", "13 - SACOLA G BOTI INST 2025", "14 - SACOLA PARDA M", "15 - SACOLA PARDA G"]
UNIDADES = ["Unidade", "Caixa", "Display"]

# --- FUNÇÕES DE SISTEMA ---
def realizar_login(nome_digitado, senha_digitada):
    try:
        user_query = supabase.table("usuarios").select("*").ilike("nome", nome_digitado).single().execute()
        if user_query.data:
            email_tecnico = user_query.data['email']
            res = supabase.auth.sign_in_with_password({"email": email_tecnico, "password": senha_digitada})
            st.session_state["usuario_logado"] = True
            st.session_state["usuario_nome"] = user_query.data["nome"]
            st.session_state["vd_usuario"] = user_query.data["loja_responsavel"]
            st.session_state["nivel_acesso"] = user_query.data["nivel_acesso"]
            st.rerun()
        else:
            st.error("Usuário não cadastrado.")
    except Exception:
        st.error("Dados de acesso incorretos.")

def admin_cadastrar_usuario(nome, vd, senha):
    try:
        email_ficticio = f"{nome.lower().replace(' ', '.')}@gmslog.com"
        new_user = supabase.auth.admin.create_user({
            "email": email_ficticio, "password": senha, "email_confirm": True
        })
        if new_user.user:
            supabase.table("usuarios").insert({
                "id": new_user.user.id, "nome": nome, "email": email_ficticio,
                "loja_responsavel": vd, "nivel_acesso": "operador"
            }).execute()
            return True, email_ficticio
    except Exception as e:
        return False, str(e)

# --- TELA DE ACESSO (LOGIN CENTRALIZADO COM LOGO) ---
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    # Espaçamento para centralizar verticalmente
    st.write("##")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        st.image("https://c5gwmsmjx1.execute-api.us-east-1.amazonaws.com/prod/dados_processo_seletivo/logo_empresa/129279/Logo_03@4x.png", use_container_width=True)
        st.markdown("<h3 style='text-align: center;'>Controle de Insumos</h3>", unsafe_allow_html=True)
        
        with st.container(border=True):
            n_login = st.text_input("Nome do Usuário")
            s_login = st.text_input("Senha", type="password")
            if st.button("ENTRAR NO SISTEMA"):
                realizar_login(n_login, s_login)
    st.stop()

# --- ÁREA LOGADA ---
st.sidebar.image("https://c5gwmsmjx1.execute-api.us-east-1.amazonaws.com/prod/dados_processo_seletivo/logo_empresa/129279/Logo_03@4x.png", width=150)
st.sidebar.markdown(f"👤 **{st.session_state['usuario_nome']}**")
st.sidebar.caption(f"📍 {st.session_state['vd_usuario']} ({st.session_state['nivel_acesso'].upper()})")

if st.sidebar.button("Sair do Sistema"):
    st.session_state["usuario_logado"] = False
    st.rerun()

menu_options = ["📊 Estoque Geral", "🔄 Movimentação"]
if st.session_state["nivel_acesso"] == "admin":
    menu_options += ["📜 Histórico Global", "⚙️ Gerenciar Sistema"]

menu = st.sidebar.selectbox("MENU", menu_options)

# 1. ESTOQUE GERAL
if menu == "📊 Estoque Geral":
    st.subheader("📊 Saldos por Unidade")
    res = supabase.table("estoque_logistica").select("*").execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        if st.session_state["nivel_acesso"] == "admin":
            filtro_vd = st.multiselect("Filtrar por VD (Vazio = Todos)", VDS)
            if filtro_vd:
                df = df[df['loja'].isin(filtro_vd)]
        else:
            df = df[df['loja'] == st.session_state['vd_usuario']]
        
        # Formatação de Datas
        if 'ultima_atualizacao' in df.columns:
            df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao']).dt.strftime('%d/%m/%Y %H:%M')
        
        cols = ["loja", "produto", "quantidade", "tipo_unidade", "ultima_atualizacao"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)

# 2. MOVIMENTAÇÃO
elif menu == "🔄 Movimentação":
    st.subheader("🔄 Registrar Saída ou Entrada")
    vd_alvo = st.session_state["vd_usuario"] if st.session_state["nivel_acesso"] == "operador" else st.selectbox("VD", VDS)
    prod_alvo = st.selectbox("Material", PRODUTOS)
    tipo_mov = st.radio("Ação", ["Saída", "Entrada"], horizontal=True)
    
    item = supabase.table("estoque_logistica").select("*").match({"loja": vd_alvo, "produto": prod_alvo}).execute()
    if item.data:
        saldo_atual = item.data[0]['quantidade']
        st.metric("Saldo Atual", saldo_atual)
        qtd = st.number_input("Quantidade", min_value=1, step=1)
        if st.button("CONFIRMAR REGISTRO"):
            novo_saldo = saldo_atual - qtd if tipo_mov == "Saída" else saldo_atual + qtd
            if novo_saldo < 0: st.error("Erro: Saldo insuficiente")
            else:
                supabase.table("estoque_logistica").update({"quantidade": novo_saldo}).eq("id", item.data[0]['id']).execute()
                supabase.table("historico_movimentacao").insert({
                    "vd": vd_alvo, "produto": prod_alvo, "tipo": tipo_mov.upper(),
                    "quantidade_movimentada": qtd, "saldo_anterior": saldo_atual,
                    "saldo_novo": novo_saldo, "usuario": st.session_state["usuario_nome"]
                }).execute()
                st.success("Estoque atualizado com sucesso!")
                st.rerun()

# 3. HISTÓRICO GLOBAL
elif menu == "📜 Histórico Global":
    st.subheader("📜 Histórico de Movimentações")
    hist = supabase.table("historico_movimentacao").select("*").order("data_movimentacao", desc=True).execute()
    if hist.data:
        df_hist = pd.DataFrame(hist.data)
        df_hist['data_movimentacao'] = pd.to_datetime(df_hist['data_movimentacao']).dt.strftime('%d/%m/%Y %H:%M')
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

# 4. GERENCIAR SISTEMA
elif menu == "⚙️ Gerenciar Sistema":
    tab1, tab2 = st.tabs(["📦 Vincular Materiais", "👥 Cadastrar Gerentes"])
    with tab1:
        with st.form("vinculo"):
            v, p, u = st.selectbox("VD", VDS), st.selectbox("Produto", PRODUTOS), st.selectbox("Unidade", UNIDADES)
            q = st.number_input("Estoque Inicial", min_value=0)
            if st.form_submit_button("VINCULAR MATERIAL"):
                supabase.table("estoque_logistica").insert({"loja": v, "produto": p, "tipo_unidade": u, "quantidade": q, "registrado_por": st.session_state["usuario_nome"]}).execute()
                st.success("Vinculado!")
    with tab2:
        with st.form("cadastro_gerente"):
            novo_nome, loja_gerente = st.text_input("Nome Completo"), st.selectbox("Loja", VDS)
            senha_gerente = st.text_input("Senha Padrão", value="gms123")
            if st.form_submit_button("CRIAR ACESSO"):
                if novo_nome:
                    sucesso, msg = admin_cadastrar_usuario(novo_nome, loja_gerente, senha_gerente)
                    if sucesso: st.success(f"Acesso criado para {novo_nome}!")
                    else: st.error(f"Erro: {msg}")

