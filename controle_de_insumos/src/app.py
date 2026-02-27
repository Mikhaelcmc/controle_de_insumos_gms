import streamlit as st
from supabase import create_client
import pandas as pd

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Logística GMS", layout="wide", page_icon="📦")

# --- 2. CSS PERSONALIZADO ---
st.markdown("""
    <style>
    .stTextInput > div > div > input { border-radius: 8px; text-align: left; }
    .stButton>button {
        width: auto; padding-left: 30px; padding-right: 30px;
        border-radius: 8px; height: 3em;
        background-color: #004684; color: white; font-weight: bold;
    }
    label { text-align: left !important; width: 100%; }
    [data-testid="stMetricValue"] { font-size: 32px; color: #004684; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONEXÃO SUPABASE ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL, KEY)

# --- 4. LISTAS FIXAS ---
VDS = ["23924-HUB", "14523-ITABATÃ", "19081-ITAMARAJU", "13483-PORTO SEGURO", "18481-TEIXEIRA", "13481-EUNÁPOLIS", "23332-BARRA"]
PRODUTOS = ["1 - Caixas Omni PP", "2 - Caixas Omni P", "3 - Caixas Omni M", "4 - Caixas entregas P", "5 - Caixas entregas M", "6 - Etiquetas entrega", "7 - Ribbon", "8 - Fita gomada", "9 - Fita adesiva", "10 - SACOLA PP BOTI INST 2025", "11 - SACOLA P BOTI INST 2025", "12 - SACOLA M BOTI INST 2025", "13 - SACOLA G BOTI INST 2025", "14 - SACOLA PARDA M", "15 - SACOLA PARDA G"]
UNIDADES = ["Unidade", "Caixa", "Display"]

# --- 5. FUNÇÕES ---
def realizar_login(nome_digitado, senha_digitada):
    try:
        user_query = supabase.table("usuarios").select("*").ilike("nome", nome_digitado).single().execute()
        if user_query.data:
            email_tecnico = user_query.data['email']
            supabase.auth.sign_in_with_password({"email": email_tecnico, "password": senha_digitada})
            st.session_state["usuario_logado"] = True
            st.session_state["usuario_nome"] = user_query.data["nome"]
            st.session_state["vd_usuario"] = user_query.data["loja_responsavel"]
            st.session_state["nivel_acesso"] = user_query.data["nivel_acesso"]
            st.rerun()
    except Exception:
        st.error("Dados de acesso incorretos.")

# --- 6. TELA DE LOGIN ---
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    c1, c2, c3 = st.columns([1.1, 1, 1.1])
    with c2:
        st.image("https://c5gwmsmjx1.execute-api.us-east-1.amazonaws.com/prod/dados_processo_seletivo/logo_empresa/129279/Logo_03@4x.png", use_container_width=True)
        st.markdown("<h4 style='text-align: center;'>Controle de Insumos 💎</h4>", unsafe_allow_html=True)
        with st.container(border=True):
            n_login = st.text_input("Nome do Usuário")
            s_login = st.text_input("Senha", type="password")
            if st.button("ENTRAR NO SISTEMA"):
                realizar_login(n_login, s_login)
    st.stop()

# --- 7. SIDEBAR ---
st.sidebar.image("https://c5gwmsmjx1.execute-api.us-east-1.amazonaws.com/prod/dados_processo_seletivo/logo_empresa/129279/Logo_03@4x.png", width=150)
st.sidebar.markdown(f"👤 **{st.session_state['usuario_nome']}**")
st.sidebar.divider()

menu = st.sidebar.selectbox("MENU", ["📊 Estoque Geral", "🔄 Movimentação", "📜 Histórico Global", "⚙️ Gerenciar Sistema"] if st.session_state["nivel_acesso"] == "admin" else ["📊 Estoque Geral", "🔄 Movimentação"])

if st.sidebar.button("🚪 Sair"):
    st.session_state["usuario_logado"] = False
    st.rerun()

# --- 8. LOGICA DAS ABAS ---

# ABA: ESTOQUE GERAL (Sempre Consolida por Loja/Produto)
if menu == "📊 Estoque Geral":
    st.subheader("📊 Saldos Atuais")
    res = supabase.table("estoque_logistica").select("*").execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        # Filtro de Acesso
        if st.session_state["nivel_acesso"] != "admin":
            df = df[df['loja'] == st.session_state['vd_usuario']]
        
        # Formatação
        df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao']).dt.strftime('%d/%m/%Y %H:%M')
        cols = ["loja", "produto", "quantidade", "tipo_unidade", "registrado_por", "ultima_atualizacao"]
        st.dataframe(df[cols].sort_values(by=['loja', 'produto']), use_container_width=True, hide_index=True)

# ABA: MOVIMENTAÇÃO (Ajustada para nunca duplicar)
elif menu == "🔄 Movimentação":
    st.subheader("🔄 Registrar Movimentação")
    vd_alvo = st.session_state["vd_usuario"] if st.session_state["nivel_acesso"] == "operador" else st.selectbox("VD", VDS)
    prod_alvo = st.selectbox("Material", PRODUTOS)
    tipo_mov = st.radio("Ação", ["Saída", "Entrada"], horizontal=True)
    
    # Busca o registro único no banco
    item = supabase.table("estoque_logistica").select("*").match({"loja": vd_alvo, "produto": prod_alvo}).execute()
    
    if item.data:
        # Se existem duplicatas no banco, pegamos a primeira e avisamos
        registro = item.data[0] 
        saldo_atual = registro['quantidade']
        
        st.metric("Saldo Atual no Sistema", f"{saldo_atual} {registro['tipo_unidade']}")
        qtd_mov = st.number_input("Quantidade da Manobra", min_value=1, step=1)
        
        if st.button("CONFIRMAR"):
            novo_saldo = saldo_atual - qtd_mov if tipo_mov == "Saída" else saldo_atual + qtd_mov
            
            if novo_saldo < 0:
                st.error("Erro: Saldo insuficiente para essa saída.")
            else:
                # 1. ATUALIZA O REGISTRO EXISTENTE (Não cria novo)
                supabase.table("estoque_logistica").update({
                    "quantidade": novo_saldo,
                    "registrado_por": st.session_state["usuario_nome"]
                }).eq("id", registro['id']).execute()
                
                # 2. GERA O LOG NO HISTÓRICO
                supabase.table("historico_movimentacao").insert({
                    "vd": vd_alvo, "produto": prod_alvo, "tipo": tipo_mov.upper(),
                    "quantidade_movimentada": qtd_mov, "saldo_anterior": saldo_atual,
                    "saldo_novo": novo_saldo, "usuario": st.session_state["usuario_nome"]
                }).execute()
                
                st.success(f"Sucesso! Novo saldo: {novo_saldo}")
                st.rerun()
    else:
        st.warning("Este produto ainda não foi vinculado a esta loja. Vá em 'Gerenciar Sistema' primeiro.")

# ABA: HISTÓRICO (Onde as linhas novas devem aparecer)
elif menu == "📜 Histórico Global":
    st.subheader("📜 Histórico de Movimentações")
    hist = supabase.table("historico_movimentacao").select("*").order("data_movimentacao", desc=True).execute()
    if hist.data:
        df_h = pd.DataFrame(hist.data)
        df_h['data_movimentacao'] = pd.to_datetime(df_h['data_movimentacao']).dt.strftime('%d/%m/%Y %H:%M')
        st.dataframe(df_h, use_container_width=True, hide_index=True)

# ABA: GERENCIAR (Para criar o vínculo inicial)
elif menu == "⚙️ Gerenciar Sistema":
    st.subheader("⚙️ Configurações")
    t1, t2 = st.tabs(["📦 Vincular Material", "👤 Usuários"])
    with t1:
        with st.form("vinculo"):
            v, p, u = st.selectbox("Loja", VDS), st.selectbox("Item", PRODUTOS), st.selectbox("Unidade", UNIDADES)
            q = st.number_input("Estoque Inicial", min_value=0)
            if st.form_submit_button("VINCULAR"):
                # Verifica se já existe antes de criar para não duplicar
                check = supabase.table("estoque_logistica").select("id").match({"loja": v, "produto": p}).execute()
                if check.data:
                    st.error("Este item já está vinculado a esta loja. Use 'Movimentação' para alterar o saldo.")
                else:
                    supabase.table("estoque_logistica").insert({"loja": v, "produto": p, "tipo_unidade": u, "quantidade": q, "registrado_por": st.session_state["usuario_nome"]}).execute()
                    st.success("Vinculado com sucesso!")
