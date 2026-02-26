import streamlit as st
from supabase import create_client
import pandas as pd

# --- CONFIGURAÇÃO SUPABASE ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL, KEY)

# --- LISTAS FIXAS ---
PRODUTOS = [
    "1 - Caixas Omni PP", "2 - Caixas Omni P", "3 - Caixas Omni M", 
    "4 - Caixas entregas P", "5 - Caixas entregas M", "6 - Etiquetas entrega", 
    "7 - Ribbon", "8 - Fita gomada", "9 - Fita adesiva", 
    "10 - SACOLA PP BOTI INST 2025", "11 - SACOLA P BOTI INST 2025", 
    "12 - SACOLA M BOTI INST 2025", "13 - SACOLA G BOTI INST 2025", 
    "14 - SACOLA PARDA M", "15 - SACOLA PARDA G"
]
UNIDADES = ["Unidade", "Caixa", "Display"]
LOJAS = [f"Loja {i:02d}" for i in range(1, 29)]

st.set_page_config(page_title="Logística Boticário GMS", layout="wide")

st.title("Sistema de Insumos Logísticos")

# --- MENU LATERAL ---
menu = st.sidebar.selectbox("Navegação", ["Estoque Geral", "Dar Saída/Entrada", "Gerenciar Produtos"])

# --- FUNÇÕES DE BANCO ---
def buscar_dados():
    res = supabase.table("estoque_logistica").select("*").execute()
    return pd.DataFrame(res.data)

# --- INTERFACE ---

if menu == "Estoque Geral":
    st.subheader("📊 Saldo Atual por Loja")
    df = buscar_dados()
    if not df.empty:
        # Filtros rápidos
        loja_f = st.multiselect("Filtrar Loja", LOJAS)
        if loja_f:
            df = df[df['loja'].isin(loja_f)]
        st.dataframe(df.drop(columns=['id']), use_container_width=True)
    else:
        st.info("Nenhum dado encontrado. Vá em 'Gerenciar' para cadastrar o estoque inicial.")

elif menu == "Dar Saída/Entrada":
    st.subheader("🔄 Movimentação de Material")
    
    col1, col2 = st.columns(2)
    with col1:
        loja_sel = st.selectbox("Loja", LOJAS)
        prod_sel = st.selectbox("Material", PRODUTOS)
    
    # Busca saldo atual no banco
    res = supabase.table("estoque_logistica").select("quantidade", "id").match({"loja": loja_sel, "produto": prod_sel}).execute()
    
    if res.data:
        saldo_atual = res.data[0]['quantidade']
        item_id = res.data[0]['id']
        st.metric("Saldo Atual", f"{saldo_atual}")
        
        qtd_mov = st.number_input("Quantidade da Movimentação (Ex: -10 para saída, 10 para entrada)", step=1)
        
        if st.button("Confirmar Movimentação"):
            novo_saldo = saldo_atual + qtd_mov
            if novo_saldo < 0:
                st.error("Erro: O estoque não pode ficar negativo!")
            else:
                supabase.table("estoque_logistica").update({"quantidade": novo_saldo}).eq("id", item_id).execute()
                st.success("Movimentação registrada com sucesso!")
                st.rerun()
    else:
        st.warning("Este produto ainda não foi cadastrado para esta loja.")

elif menu == "Gerenciar Produtos":
    st.subheader("⚙️ Cadastro e Edição")
    
    tab1, tab2 = st.tabs(["Novo Produto/Loja", "Excluir Registro"])
    
    with tab1:
        with st.form("cadastro"):
            l = st.selectbox("Selecione a Loja", LOJAS)
            p = st.selectbox("Selecione o Material", PRODUTOS)
            u = st.selectbox("Unidade de Medida", UNIDADES)
            q = st.number_input("Estoque Inicial", min_value=0)
            if st.form_submit_button("Salvar Registro"):
                # Verifica se já existe para não duplicar
                check = supabase.table("estoque_logistica").select("*").match({"loja": l, "produto": p}).execute()
                if check.data:
                    st.error("Este produto já está cadastrado nesta loja! Use a aba de Movimentação.")
                else:
                    supabase.table("estoque_logistica").insert({"loja": l, "produto": p, "tipo_unidade": u, "quantidade": q}).execute()
                    st.success("Cadastrado com sucesso!")

    with tab2:
        df_excluir = buscar_dados()
        if not df_excluir.empty:
            id_excluir = st.selectbox("Selecionar item para DELETAR", df_excluir['id'].tolist(), 
                                      format_func=lambda x: f"ID {x} - {df_excluir[df_excluir['id']==x]['loja'].values[0]} - {df_excluir[df_excluir['id']==x]['produto'].values[0]}")
            if st.button("❌ EXCLUIR PERMANENTEMENTE", type="primary"):
                supabase.table("estoque_logistica").delete().eq("id", id_excluir).execute()
                st.success("Registro removido.")
                st.rerun()