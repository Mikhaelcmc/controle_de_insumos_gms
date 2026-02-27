import streamlit as st
from supabase import create_client
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Logística GMS", layout="wide", page_icon="📦")

# --- CSS PARA MELHORAR O LAYOUT ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #1f77b4; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
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
            "email": email_ficticio,
            "password": senha,
            "email_confirm": True
        })
        
        if new_user.user:
            user_id = new_user.user.id
            supabase.table("usuarios").insert({
                "id": user_id, "nome": nome, "email": email_ficticio,
                "loja_responsavel": vd, "nivel_acesso": "operador"
            }).execute()
            return True, email_ficticio
    except Exception as e:
        return False, str(e)

# --- TELA DE ACESSO (LOGIN CENTRALIZADO) ---
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.write("") # Espaçador
        # Coloque o link da sua logo abaixo
        st.image("https://seu-link-da-logo.com/logo.png", width=250) 
        st.title("🔐 Logística GMS")
        
        with st.container(border=True):
            n_login = st.text_input("Seu Nome")
            s_login = st.text_input("Sua Senha", type="password")
            if st.button("Acessar"):
                realizar_login(n_login, s_login)
    st.stop()

# --- ÁREA LOGADA ---
st.sidebar.markdown(f"### Bem-vindo, \n**{st.session_state['usuario_nome']}**")
st.sidebar.info(f"📍 {st.session_state['vd_usuario']} | {st.session_state['nivel_acesso'].upper()}")

if st.sidebar.button("Sair"):
    st.session_state["usuario_logado"] = False
    st.rerun()

menu_options = ["📊 Estoque Geral", "🔄 Movimentação"]
if st.session_state["nivel_acesso"] == "admin":
    menu_options += ["📜 Histórico Global", "⚙️ Gerenciar Sistema"]

menu = st.sidebar.selectbox("Navegação", menu_options)

# 1. ESTOQUE GERAL (COM FILTRO ADMIN)
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
        
        if 'ultima_atualizacao' in df.columns:
            df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao'])
            df['Dia'] = df['ultima_atualizacao'].dt.day
            df['Mês'] = df['ultima_atualizacao'].dt.month
            df['Ano'] = df['ultima_atualizacao'].dt.year
        
        cols = ["loja", "produto", "quantidade", "tipo_unidade", "Dia", "Mês", "Ano"]
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
        st.metric("Saldo em Estoque", saldo_atual)
        qtd = st.number_input("Quantidade", min_value=1)
        if st.button("Confirmar Movimentação"):
            novo_saldo = saldo_atual - qtd if tipo_mov == "Saída" else saldo_atual + qtd
            if novo_saldo < 0: st.error("Erro: Saldo insuficiente")
            else:
                supabase.table("estoque_logistica").update({"quantidade": novo_saldo}).eq("id", item.data[0]['id']).execute()
                supabase.table("historico_movimentacao").insert({
                    "vd": vd_alvo, "produto": prod_alvo, "tipo": tipo_mov.upper(),
                    "quantidade_movimentada": qtd, "saldo_anterior": saldo_atual,
                    "saldo_novo": novo_saldo, "usuario": st.session_state["usuario_nome"]
                }).execute()
                st.success("Estoque atualizado!")
                st.rerun()

# 4. GERENCIAR SISTEMA
elif menu == "⚙️ Gerenciar Sistema":
    tab1, tab2 = st.tabs(["📦 Vincular Materiais", "👥 Cadastrar Gerentes"])
    
    with tab1:
        with st.form("vinculo"):
            v = st.selectbox("VD", VDS)
            p = st.selectbox("Produto", PRODUTOS)
            u = st.selectbox("Unidade", UNIDADES)
            q = st.number_input("Estoque Inicial", min_value=0)
            if st.form_submit_button("Vincular Material"):
                supabase.table("estoque_logistica").insert({"loja": v, "produto": p, "tipo_unidade": u, "quantidade": q, "registrado_por": st.session_state["usuario_nome"]}).execute()
                st.success("Material vinculado ao VD com sucesso!")

    with tab2:
        with st.form("cadastro_gerente"):
            novo_nome = st.text_input("Nome Completo do Gerente")
            loja_gerente = st.selectbox("Loja Responsável", VDS)
            senha_gerente = st.text_input("Senha Padrão", value="gms123")
            if st.form_submit_button("Criar Acesso"):
                if novo_nome:
                    sucesso, msg = admin_cadastrar_usuario(novo_nome, loja_gerente, senha_gerente)
                    if sucesso: st.success(f"Acesso criado para {novo_nome}!")
                    else: st.error(f"Erro: {msg}")

