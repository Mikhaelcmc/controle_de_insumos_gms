import streamlit as st
from supabase import create_client
import pandas as pd

# --- CONFIGURAÇÃO SUPABASE ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL, KEY)

# --- LISTAS FIXAS ---
VDS = ["23924-HUB", "14523-ITABATÃ", "19081-ITAMARAJU", "13483-PORTO SEGURO", "18481-TEIXEIRA", "13481-EUNÁPOLIS", "23332-BARRA"]
PRODUTOS = ["1 - Caixas Omni PP", "2 - Caixas Omni P", "3 - Caixas Omni M", "4 - Caixas entregas P", "5 - Caixas entregas M", "6 - Etiquetas entrega", "7 - Ribbon", "8 - Fita gomada", "9 - Fita adesiva", "10 - SACOLA PP BOTI INST 2025", "11 - SACOLA P BOTI INST 2025", "12 - SACOLA M BOTI INST 2025", "13 - SACOLA G BOTI INST 2025", "14 - SACOLA PARDA M", "15 - SACOLA PARDA G"]
UNIDADES = ["Unidade", "Caixa", "Display"]

st.set_page_config(page_title="Logística GMS", layout="wide")

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
        # 1. Criamos um email fictício baseado no nome para o Auth
        email_ficticio = f"{nome.lower().replace(' ', '.')}@gmslog.com"
        
        # 2. Cria o usuário no Authentication (Auth Admin API)
        # Nota: Em algumas versões do SDK, usamos auth.admin.create_user
        new_user = supabase.auth.admin.create_user({
            "email": email_ficticio,
            "password": senha,
            "email_confirm": True
        })
        
        # 3. Se deu certo, pegamos o ID e inserimos na nossa tabela 'usuarios'
        if new_user.user:
            user_id = new_user.user.id
            supabase.table("usuarios").insert({
                "id": user_id,
                "nome": nome,
                "email": email_ficticio,
                "loja_responsavel": vd,
                "nivel_acesso": "operador"
            }).execute()
            return True, email_ficticio
    except Exception as e:
        return False, str(e)

# --- TELA DE ACESSO ---
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.title("🔐 Logística GMS")
    n_login = st.text_input("Seu Nome")
    s_login = st.text_input("Sua Senha", type="password")
    if st.button("Acessar", use_container_width=True):
        realizar_login(n_login, s_login)
    st.stop()

# --- ÁREA LOGADA ---
st.sidebar.title(f" {st.session_state['usuario_nome']}")
st.sidebar.info(f" {st.session_state['vd_usuario']} ({st.session_state['nivel_acesso'].upper()})")

if st.sidebar.button("Sair"):
    st.session_state["usuario_logado"] = False
    st.rerun()

menu_options = ["📊 Estoque Geral", "🔄 Movimentação"]
if st.session_state["nivel_acesso"] == "admin":
    menu_options += ["📜 Histórico Global", "⚙️ Gerenciar Sistema"]

menu = st.sidebar.selectbox("Menu", menu_options)

# 1. ESTOQUE GERAL
if menu == "📊 Estoque Geral":
    st.subheader("Saldos por Unidade")
    res = supabase.table("estoque_logistica").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        if st.session_state["nivel_acesso"] == "operador":
            df = df[df['loja'] == st.session_state['vd_usuario']]
        
        if 'ultima_atualizacao' in df.columns:
            df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao'])
            df['Dia'] = df['ultima_atualizacao'].dt.day
            df['Mês'] = df['ultima_atualizacao'].dt.month
            df['Ano'] = df['ultima_atualizacao'].dt.year
        
        cols = ["loja", "produto", "quantidade", "tipo_unidade", "Dia", "Mês", "Ano", "registrado_por"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True)

# 2. MOVIMENTAÇÃO
elif menu == "🔄 Movimentação":
    st.subheader("Registrar Saída ou Entrada")
    vd_alvo = st.session_state["vd_usuario"] if st.session_state["nivel_acesso"] == "operador" else st.selectbox("VD", VDS)
    prod_alvo = st.selectbox("Material", PRODUTOS)
    tipo_mov = st.radio("Ação", ["Saída", "Entrada"])
    
    item = supabase.table("estoque_logistica").select("*").match({"loja": vd_alvo, "produto": prod_alvo}).execute()
    if item.data:
        saldo_atual = item.data[0]['quantidade']
        st.metric("Saldo Atual", saldo_atual)
        qtd = st.number_input("Qtd", min_value=1)
        if st.button("Salvar"):
            novo_saldo = saldo_atual - qtd if tipo_mov == "Saída" else saldo_atual + qtd
            if novo_saldo < 0: st.error("Saldo insuficiente")
            else:
                supabase.table("estoque_logistica").update({"quantidade": novo_saldo}).eq("id", item.data[0]['id']).execute()
                supabase.table("historico_movimentacao").insert({
                    "vd": vd_alvo, "produto": prod_alvo, "tipo": tipo_mov.upper(),
                    "quantidade_movimentada": qtd, "saldo_anterior": saldo_atual,
                    "saldo_novo": novo_saldo, "usuario": st.session_state["usuario_nome"]
                }).execute()
                st.success("Sucesso!")
                st.rerun()

# 4. GERENCIAR SISTEMA (AQUI ESTÁ A NOVIDADE)
elif menu == "⚙️ Gerenciar Sistema":
    tab1, tab2 = st.tabs(["Vincular Materiais", "👥 Cadastrar Gerentes"])
    
    with tab1:
        with st.form("vinculo"):
            v = st.selectbox("VD", VDS)
            p = st.selectbox("Produto", PRODUTOS)
            u = st.selectbox("Unidade", UNIDADES)
            q = st.number_input("Estoque Inicial", min_value=0)
            if st.form_submit_button("Vincular"):
                supabase.table("estoque_logistica").insert({"loja": v, "produto": p, "tipo_unidade": u, "quantidade": q, "registrado_por": st.session_state["usuario_nome"]}).execute()
                st.success("Vinculado!")

    with tab2:
        st.write("Crie o acesso para os gerentes das lojas aqui.")
        with st.form("cadastro_gerente"):
            novo_nome = st.text_input("Nome Completo do Gerente")
            loja_gerente = st.selectbox("Loja Responsável", VDS)
            senha_gerente = st.text_input("Senha Padrão", value="gms123", type="password")
            
            if st.form_submit_button("Cadastrar Gerente"):
                if novo_nome:
                    sucesso, msg = admin_cadastrar_usuario(novo_nome, loja_gerente, senha_gerente)
                    if sucesso:
                        st.success(f"Gerente {novo_nome} cadastrado! E-mail técnico: {msg}")
                    else:
                        st.error(f"Erro ao cadastrar: {msg}")
