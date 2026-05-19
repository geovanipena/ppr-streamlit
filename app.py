"""
PPR Web – Gerador de Plano de Proteção Radiológica
Versão Streamlit  |  Física Médica / Radioterapia
"""
import streamlit as st
import json, io, base64, tempfile, os, hashlib
from copy import deepcopy
import pandas as pd

st.set_page_config(
    page_title="Gerador de PPR ☢️",
    page_icon="☢️",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
h1  { color: #1B3A6B; }
h2  { color: #1B3A6B; font-size: 1.1rem; margin-top: 1rem; }
h3  { color: #2E86C1; font-size: 1rem; }
.sec-hdr {
    background:#EBF5FB; padding:6px 12px;
    border-left:4px solid #1B3A6B;
    border-radius:4px; margin:10px 0 4px 0;
    font-weight:700; color:#1B3A6B; font-size:.95rem;
}
.stTabs [data-baseweb="tab"] { font-weight:600; }
.stTabs [aria-selected="true"] {
    background:#1B3A6B !important; color:white !important;
}
</style>
""", unsafe_allow_html=True)

def sec(txt): st.markdown(f'<div class="sec-hdr">{txt}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  DADOS PADRÃO
# ═══════════════════════════════════════════════════════════════════════════════
def dados_padrao() -> dict:
    return {
        "instalacao": {k: "" for k in [
            "nome","matricula_cnen","cnpj","rua","complemento","bairro",
            "cidade","uf","cep","telefone","horario","objetivo",
            "grupo","subgrupo","instituicao","cidade_data","mes","ano",
        ]},
        "responsaveis": [],
        "supervisor":            {"nome":"","rt":"","ra":""},
        "substituto_supervisor": {"nome":"","rt":"","ra":""},
        "responsavel_tecnico":   {"nome":"","crm":"","cb":""},
        "substituto_rt":         {"nome":"","crm":"","cb":""},
        "diretor_clinico":       {"nome":"","crm":"","cb":""},
        "equipes_medicos":[],"equipes_fisicos":[],"equipes_tecnicos":[],
        "equipes_dosimetristas":[],"equipes_enfermagem":[],"equipes_demais":[],
        "asos":[],
        "equipamentos":[],"fontes_referencia":[],"conjunto_dosimetrico":[],
        "instrumentos_medicao":[],"outros_detectores":[],"fantomas":[],
        "monitores_area":[],
        "testes_diarios":[],"testes_mensais":[],"testes_anuais":[],
        "testes_diarios_braqui":[],"testes_trimestrais_braqui":[],
        "testes_mensais_orto":[],
        "sistemas_planejamento":[],"tecnicas_tratamento":[],
        "textos_caps": {k: "" for k in [
            "classificacao_areas","controle_acesso","monitoracao_individual",
            "monitoracao_areas","controle_medico","niveis_operacionais",
            "procedimentos_emergencia","programa_treinamento",
            "programa_educacao","gerencia_rejeitos","calculo_barreiras",
            "matriz_risco","auditoria_externa",
        ]},
        "pdfs": {k: [] for k in [
            "autorizacao_funcionamento","certificados_conjunto_dosimetrico",
            "certificados_monitores_area","certificados_outros",
            "sevrra","auditoria","calculo_blindagem","levantamento_radiometrico",
            "contrato_monitoracao","classificacao_areas","procedimentos_emergencia",
            "gerencia_rejeitos",
        ]},
        "imagens": {"logo":"","classificacao_areas":[],"gerencia_rejeitos":[]},
        # Armazenamento de bytes dos PDFs enviados via upload (base64)
        "_pdfs_bytes": {},
        "_logo_bytes": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  IMPORTAÇÃO — suporte ao formato antigo (7 arquivos .txt/.json separados)
#  e ao formato novo (1 arquivo JSON unificado)
# ═══════════════════════════════════════════════════════════════════════════════

def _mesclar_arquivo(base: dict, nome: str, conteudo: dict) -> dict:
    """
    Detecta o tipo do arquivo pelo nome e mescla no dict `base`.

    Formatos aceitos:
      instalacao.json  → chaves diretas (sem wrapper)
      pessoal.json     → chaves diretas (responsaveis, supervisor, equipes_*)
      equipamentos.json→ chaves diretas (equipamentos, fontes_referencia, …)
      qualidade.json   → chaves diretas (testes_*, sistemas_planejamento, …)
      textos.json      → {"textos_caps": {...}}
      pdfs.json        → {"pdfs": {...}}
      imagens.json     → {"imagens": {...}}
    """
    nome_lower = nome.lower().replace(".txt", "").replace(".json", "")

    if nome_lower == "instalacao":
        # pode vir com ou sem wrapper {"instalacao": {...}}
        if "instalacao" in conteudo and isinstance(conteudo["instalacao"], dict):
            base["instalacao"].update(conteudo["instalacao"])
        else:
            base["instalacao"].update(conteudo)

    elif nome_lower == "pessoal":
        # chaves diretas no root
        chaves_pessoal = [
            "responsaveis", "supervisor", "substituto_supervisor",
            "responsavel_tecnico", "substituto_rt", "diretor_clinico",
            "equipes_medicos", "equipes_fisicos", "equipes_tecnicos",
            "equipes_dosimetristas", "equipes_enfermagem", "equipes_demais", "asos",
        ]
        for k in chaves_pessoal:
            if k in conteudo:
                base[k] = conteudo[k]

    elif nome_lower == "equipamentos":
        chaves_eq = [
            "equipamentos", "fontes_referencia", "conjunto_dosimetrico",
            "instrumentos_medicao", "outros_detectores", "fantomas", "monitores_area",
        ]
        for k in chaves_eq:
            if k in conteudo:
                base[k] = conteudo[k]

    elif nome_lower == "qualidade":
        chaves_gq = [
            "testes_diarios", "testes_mensais", "testes_anuais",
            "testes_diarios_braqui", "testes_trimestrais_braqui",
            "testes_mensais_orto", "sistemas_planejamento", "tecnicas_tratamento",
        ]
        for k in chaves_gq:
            if k in conteudo:
                base[k] = conteudo[k]

    elif nome_lower == "textos":
        # pode vir como {"textos_caps": {...}} ou diretamente {"classificacao_areas": ...}
        if "textos_caps" in conteudo:
            base["textos_caps"].update(conteudo["textos_caps"])
        else:
            base["textos_caps"].update(conteudo)

    elif nome_lower == "pdfs":
        # pode vir como {"pdfs": {...}} ou direto
        src = conteudo.get("pdfs", conteudo)
        if isinstance(src, dict):
            base["pdfs"].update(src)

    elif nome_lower == "imagens":
        # pode vir como {"imagens": {...}} ou direto
        src = conteudo.get("imagens", conteudo)
        if isinstance(src, dict):
            # logo pode ser string ou lista — normaliza para string
            if "logo" in src:
                logo = src["logo"]
                src["logo"] = logo[0] if isinstance(logo, list) and logo else (logo or "")
            base["imagens"].update(src)

    else:
        # Arquivo unificado (novo formato exportado pelo app)
        # Mescla tudo diretamente, preservando chaves internas
        for k, v in conteudo.items():
            if k.startswith("_"):
                continue  # ignora _pdfs_bytes, _logo_bytes
            if k == "instalacao" and isinstance(v, dict):
                base["instalacao"].update(v)
            elif k == "textos_caps" and isinstance(v, dict):
                base["textos_caps"].update(v)
            elif k == "pdfs" and isinstance(v, dict):
                base["pdfs"].update(v)
            elif k == "imagens" and isinstance(v, dict):
                base["imagens"].update(v)
            else:
                base[k] = v

    return base


def importar_jsons(arquivos) -> dict:
    """
    Recebe lista de UploadedFile e devolve um dict de dados completo.
    Aceita 1 arquivo (formato novo) ou vários arquivos separados (formato antigo).
    """
    base = dados_padrao()

    for arq in arquivos:
        try:
            conteudo = json.loads(arq.read())
            nome_sem_ext = arq.name.rsplit(".", 1)[0]  # tira extensão
            base = _mesclar_arquivo(base, nome_sem_ext, conteudo)
        except Exception as e:
            st.warning(f"⚠️ Erro ao ler **{arq.name}**: {e}")

    return base


# ── Session state ─────────────────────────────────────────────────────────────
if "dados" not in st.session_state:
    st.session_state.dados = dados_padrao()
if "sv" not in st.session_state:
    st.session_state.sv = 0
if "hash_salvo" not in st.session_state:
    st.session_state.hash_salvo = ""   # hash dos dados na última exportação

d = st.session_state.dados
sv = st.session_state.sv


# ═══════════════════════════════════════════════════════════════════════════════
#  FUNÇÕES DE PROGRESSO E VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _hash_dados(dados: dict) -> str:
    """Hash MD5 dos dados (sem bytes binários) para detectar mudanças."""
    exportar = {k: v for k, v in dados.items() if not k.startswith("_")}
    return hashlib.md5(json.dumps(exportar, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def calcular_progresso(dados: dict) -> tuple:
    """
    Retorna (pct: int, itens: list[dict]) onde cada item tem
    {label, ok, critico} para montar o checklist.
    """
    inst = dados.get("instalacao", {})
    itens = [
        # ── Identificação ──────────────────────────────────────────────
        {"label": "Nome da instalação",         "ok": bool(inst.get("nome")),           "critico": True},
        {"label": "Matrícula CNEN",             "ok": bool(inst.get("matricula_cnen")), "critico": True},
        {"label": "CNPJ",                       "ok": bool(inst.get("cnpj")),           "critico": True},
        {"label": "Endereço completo",          "ok": all(inst.get(k) for k in ["rua","cidade","uf","cep"]), "critico": False},
        {"label": "Grupo/Subgrupo CNEN",        "ok": bool(inst.get("grupo")),          "critico": True},
        {"label": "Objetivo da instalação",     "ok": bool(inst.get("objetivo")),       "critico": False},
        # ── Responsáveis ───────────────────────────────────────────────
        {"label": "Titular(es) cadastrado(s)",  "ok": len(dados.get("responsaveis",[])) > 0, "critico": True},
        {"label": "SPR (nome + RT + RA)",       "ok": all(dados.get("supervisor",{}).get(k) for k in ["nome","rt","ra"]), "critico": True},
        {"label": "Substituto do SPR",          "ok": bool(dados.get("substituto_supervisor",{}).get("nome")), "critico": True},
        {"label": "Responsável Técnico",        "ok": all(dados.get("responsavel_tecnico",{}).get(k) for k in ["nome","crm"]), "critico": True},
        {"label": "Substituto do RT",           "ok": bool(dados.get("substituto_rt",{}).get("nome")), "critico": False},
        # ── Equipes ────────────────────────────────────────────────────
        {"label": "Médicos cadastrados",        "ok": len(dados.get("equipes_medicos",[])) > 0,   "critico": True},
        {"label": "Físicos médicos",            "ok": len(dados.get("equipes_fisicos",[])) > 0,   "critico": True},
        {"label": "Técnicos em RT",             "ok": len(dados.get("equipes_tecnicos",[])) > 0,  "critico": False},
        # ── Equipamentos ───────────────────────────────────────────────
        {"label": "Equipamentos/Fontes",        "ok": len(dados.get("equipamentos",[])) > 0,      "critico": True},
        {"label": "Conjuntos dosimétricos",     "ok": len(dados.get("conjunto_dosimetrico",[])) > 0, "critico": True},
        {"label": "Monitores de área",          "ok": len(dados.get("monitores_area",[])) > 0,    "critico": False},
        # ── Garantia da Qualidade ──────────────────────────────────────
        {"label": "Testes diários definidos",   "ok": len(dados.get("testes_diarios",[])) > 0,    "critico": True},
        {"label": "Testes mensais definidos",   "ok": len(dados.get("testes_mensais",[])) > 0,    "critico": True},
        {"label": "Testes anuais definidos",    "ok": len(dados.get("testes_anuais",[])) > 0,     "critico": True},
        {"label": "Sistemas de planejamento",   "ok": len(dados.get("sistemas_planejamento",[])) > 0, "critico": False},
        # ── Textos ─────────────────────────────────────────────────────
        {"label": "Texto: Classificação de áreas",     "ok": bool(dados.get("textos_caps",{}).get("classificacao_areas")),    "critico": True},
        {"label": "Texto: Monitoração individual",     "ok": bool(dados.get("textos_caps",{}).get("monitoracao_individual")), "critico": True},
        {"label": "Texto: Procedimentos de emergência","ok": bool(dados.get("textos_caps",{}).get("procedimentos_emergencia")),"critico": True},
        {"label": "Texto: Gerência de rejeitos",       "ok": bool(dados.get("textos_caps",{}).get("gerencia_rejeitos")),     "critico": False},
        {"label": "Texto: Cálculo de barreiras",       "ok": bool(dados.get("textos_caps",{}).get("calculo_barreiras")),    "critico": False},
    ]
    total = len(itens)
    ok_count = sum(1 for i in itens if i["ok"])
    return int(ok_count / total * 100), itens


def erros_criticos(itens: list) -> list:
    """Retorna itens críticos não preenchidos."""
    return [i for i in itens if i["critico"] and not i["ok"]]


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS PARA TABELAS (data_editor)
# ═══════════════════════════════════════════════════════════════════════════════

def tabela_editavel(chave: str, colunas: list, altura: int = 250) -> list:
    """
    Renderiza um st.data_editor para d[chave] (lista de dicts).
    colunas: lista de (key, label)
    Retorna a lista atualizada.
    """
    col_cfg = {c[0]: st.column_config.TextColumn(c[1]) for c in colunas}
    df_ini = pd.DataFrame(d.get(chave, []) or [], columns=[c[0] for c in colunas])
    # Garante que todas as colunas existam
    for c in colunas:
        if c[0] not in df_ini.columns:
            df_ini[c[0]] = ""
    df_ini = df_ini[[c[0] for c in colunas]]

    df_edit = st.data_editor(
        df_ini,
        column_config=col_cfg,
        num_rows="dynamic",
        width='stretch',
        height=altura,
        key=f"editor_{chave}_{sv}",
    )
    # Converte de volta para lista de dicts, ignorando linhas completamente vazias
    rows = df_edit.to_dict("records")
    rows = [r for r in rows if any(str(v).strip() for v in r.values())]
    d[chave] = rows
    return rows


def bloco_resp(titulo: str, chave: str, campos: list):
    """Bloco compacto de campos para responsáveis."""
    with st.expander(titulo, expanded=False):
        val = d.get(chave, {})
        cols = st.columns(len(campos))
        for i, (k, lbl) in enumerate(campos):
            val[k] = cols[i].text_input(lbl, val.get(k, ""), key=f"{chave}_{k}_{sv}")
        d[chave] = val


# ═══════════════════════════════════════════════════════════════════════════════
#  UPLOAD DE PDFs — helper
# ═══════════════════════════════════════════════════════════════════════════════

def upload_pdfs(chave_pdfs: str, label: str):
    """Widget de upload de múltiplos PDFs para uma seção."""
    uploaded = st.file_uploader(
        label, type=["pdf"], accept_multiple_files=True,
        key=f"up_{chave_pdfs}"
    )
    if uploaded:
        if "_pdfs_bytes" not in d:
            d["_pdfs_bytes"] = {}
        for f in uploaded:
            b64 = base64.b64encode(f.read()).decode()
            key = f"{chave_pdfs}__{f.name}"
            d["_pdfs_bytes"][key] = {"nome": f.name, "data": b64, "chave_secao": chave_pdfs}
        st.success(f"✅ {len(uploaded)} arquivo(s) carregado(s)")

    # Lista arquivos já carregados nessa seção
    if d.get("_pdfs_bytes"):
        arqs = [v["nome"] for k, v in d["_pdfs_bytes"].items()
                if v.get("chave_secao") == chave_pdfs]
        if arqs:
            st.caption("Arquivos carregados: " + " · ".join(arqs))


# ═══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════════════════

# Calcula progresso e detecta mudanças não salvas
pct_prog, itens_prog = calcular_progresso(d)
hash_atual = _hash_dados(d)
dados_modificados = (hash_atual != st.session_state.hash_salvo) and bool(d["instalacao"].get("nome"))

# Linha 1: título + importar + exportar + novo
c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
with c1:
    st.title("☢️ Gerador de PPR")
    nome_inst = d["instalacao"].get("nome") or "Nova Instalação"
    st.caption(f"Plano de Proteção Radiológica  |  {nome_inst}")

with c2:
    arqs_imp = st.file_uploader(
        "📂 Importar JSON(s)",
        type=["json", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="import_json",
        help="Selecione 1 arquivo unificado (novo) OU 7 arquivos separados do formato antigo.",
    )
    if arqs_imp:
        try:
            novo = importar_jsons(arqs_imp)
            novo["_pdfs_bytes"] = d.get("_pdfs_bytes", {})
            novo["_logo_bytes"] = d.get("_logo_bytes")
            keys_preservar = {"dados", "sv", "hash_salvo"}
            for k in list(st.session_state.keys()):
                if k not in keys_preservar:
                    del st.session_state[k]
            st.session_state.dados = novo
            st.session_state.sv += 1
            st.session_state.hash_salvo = _hash_dados(novo)  # importado = "salvo"
            nomes = ", ".join(a.name for a in arqs_imp)
            st.success(f"✅ Importado: {nomes}")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao importar: {e}")

with c3:
    exportar = deepcopy(d)
    exportar.pop("_pdfs_bytes", None)
    exportar.pop("_logo_bytes", None)
    json_str = json.dumps(exportar, ensure_ascii=False, indent=2)
    nome_arq = (d["instalacao"].get("nome") or "PPR")[:25].replace(" ", "_")
    if st.download_button(
        "💾 Exportar .json",
        data=json_str.encode("utf-8"),
        file_name=f"PPR_{nome_arq}.json",
        mime="application/json",
    ):
        st.session_state.hash_salvo = hash_atual  # marca como salvo

with c4:
    if st.button("🆕 Novo Projeto", type="secondary"):
        keys_preservar = {"sv"}
        for k in list(st.session_state.keys()):
            if k not in keys_preservar:
                del st.session_state[k]
        st.session_state.dados = dados_padrao()
        st.session_state.sv += 1
        st.session_state.hash_salvo = ""
        st.rerun()

# ── Barra de progresso + alerta de não salvo ──────────────────────────────
col_prog, col_aviso = st.columns([3, 2])
with col_prog:
    cor = "#1E8449" if pct_prog >= 80 else "#E67E22" if pct_prog >= 50 else "#C0392B"
    st.markdown(
        f"""
        <div style="margin:4px 0 2px 0; font-size:.85rem; color:#555;">
            Preenchimento do PPR: <b style="color:{cor}">{pct_prog}%</b>
        </div>
        <div style="background:#eee; border-radius:8px; height:10px; overflow:hidden;">
            <div style="width:{pct_prog}%; background:{cor}; height:100%; 
                        border-radius:8px; transition:width .4s;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_aviso:
    if dados_modificados:
        st.markdown(
            """<div style="background:#FFF3CD; border:1px solid #FFC107; border-radius:6px;
                padding:6px 12px; font-size:.85rem; color:#856404; text-align:center;">
                ⚠️ <b>Dados não salvos</b> — Exporte o JSON para não perder!</div>""",
            unsafe_allow_html=True,
        )

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
#  TABS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs([
    "🏥 Instalação",
    "👥 Pessoal",
    "⚙️ Equipamentos",
    "✅ Garantia da Qualidade",
    "📝 Textos",
    "🗂️ Arquivos PDFs",
    "📑 Gerar PDF",
])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 1 – INSTALAÇÃO
# ───────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    inst = d["instalacao"]
    sec("Identificação")
    c1, c2 = st.columns(2)
    with c1:
        inst["nome"]          = st.text_input("Nome da Instituição", inst.get("nome",""), key=f"inst_nome_{sv}")
        inst["matricula_cnen"]= st.text_input("Matrícula CNEN", inst.get("matricula_cnen",""), key=f"inst_matricula_cnen_{sv}")
        inst["cnpj"]          = st.text_input("CNPJ", inst.get("cnpj",""), key=f"inst_cnpj_{sv}")
        inst["objetivo"]      = st.text_area("Objetivo", inst.get("objetivo",""), key=f"inst_objetivo_{sv}", height=80)
        inst["horario"]       = st.text_input("Horário de Funcionamento", inst.get("horario",""), key=f"inst_horario_{sv}")
        inst["telefone"]      = st.text_input("Telefone", inst.get("telefone",""), key=f"inst_telefone_{sv}")
    with c2:
        inst["rua"]           = st.text_input("Rua / Av.", inst.get("rua",""), key=f"inst_rua_{sv}")
        a, b = st.columns([1,2])
        inst["complemento"]   = a.text_input("Número", inst.get("complemento",""))
        inst["bairro"]        = b.text_input("Bairro", inst.get("bairro",""))
        a, b, c = st.columns([3,1,2])
        inst["cidade"]        = a.text_input("Cidade", inst.get("cidade",""), key=f"inst_cidade_{sv}")
        inst["uf"]            = b.text_input("UF", inst.get("uf",""), key=f"inst_uf_{sv}")
        inst["cep"]           = c.text_input("CEP", inst.get("cep",""), key=f"inst_cep_{sv}")
        a, b = st.columns(2)
        inst["grupo"]         = a.text_input("Grupo CNEN", inst.get("grupo",""), key=f"inst_grupo_{sv}")
        inst["subgrupo"]      = b.text_input("Subgrupo", inst.get("subgrupo",""), key=f"inst_subgrupo_{sv}")
        inst["instituicao"]   = st.text_input("Cabeçalho (instituição)", inst.get("instituicao",""), key=f"inst_instituicao_{sv}")

    sec("Dados do Documento")
    a, b, c = st.columns(3)
    inst["cidade_data"] = a.text_input("Cidade (rodapé)", inst.get("cidade_data",""), key=f"inst_cidade_data_{sv}")
    inst["mes"]         = b.text_input("Mês", inst.get("mes",""), key=f"inst_mes_{sv}")
    inst["ano"]         = c.text_input("Ano", inst.get("ano",""), key=f"inst_ano_{sv}")


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 2 – PESSOAL
# ───────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    sub = st.tabs(["👤 Responsáveis", "👨‍⚕️ Médicos", "🔬 Físicos",
                   "🛠️ Técnicos", "📐 Dosimetristas", "🩺 Enfermagem",
                   "👥 Demais IOEs", "🏥 ASOs"])

    # ── Responsáveis ────────────────────────────────────────────────────────────
    with sub[0]:
        sec("Titulares da Instalação")
        tabela_editavel("responsaveis",
            [("nome","Nome"),("cpf","CPF"),("cargo","Cargo")], altura=180)

        sec("Supervisor de Radioproteção (SPR)")
        bloco_resp("SPR", "supervisor",
            [("nome","Nome"),("rt","CNEN RT"),("ra","CNEN RA")])
        bloco_resp("Substituto do SPR", "substituto_supervisor",
            [("nome","Nome"),("rt","CNEN RT"),("ra","CNEN RA")])

        sec("Responsável Técnico (RT)")
        bloco_resp("Responsável Técnico", "responsavel_tecnico",
            [("nome","Nome"),("crm","CRM"),("cb","CB")])
        bloco_resp("Substituto do RT", "substituto_rt",
            [("nome","Nome"),("crm","CRM"),("cb","CB")])

        sec("Diretor Clínico")
        bloco_resp("Diretor Clínico", "diretor_clinico",
            [("nome","Nome"),("crm","CRM"),("cb","CB")])

    with sub[1]:
        sec("Equipe de Radio-Oncologistas")
        tabela_editavel("equipes_medicos",
            [("nome","Nome"),("crm","CRM"),("rb","RB"),("carga","Carga")])

    with sub[2]:
        sec("Equipe de Físicos Médicos")
        tabela_editavel("equipes_fisicos",
            [("nome","Nome"),("rt","RT"),("ra","RA"),("formacao","Formação"),("carga","Carga")])

    with sub[3]:
        sec("Equipe de Técnicos em Radioterapia")
        tabela_editavel("equipes_tecnicos",
            [("nome","Nome"),("crtr","CRTR"),("carga","Carga")])

    with sub[4]:
        sec("Equipe de Dosimetristas")
        tabela_editavel("equipes_dosimetristas",
            [("nome","Nome"),("registro","Registro"),("carga","Carga")])

    with sub[5]:
        sec("Equipe de Enfermagem")
        tabela_editavel("equipes_enfermagem",
            [("nome","Nome"),("coren","COREN"),("carga","Carga")])

    with sub[6]:
        sec("Demais IOEs")
        tabela_editavel("equipes_demais",
            [("nome","Nome"),("cargo","Cargo"),("carga","Carga")])

    with sub[7]:
        sec("ASOs – Atestados de Saúde Ocupacional")
        tabela_editavel("asos",
            [("nome","IOE"),("ultimo","Último ASO"),("validade","Validade")])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 3 – EQUIPAMENTOS
# ───────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    sub = st.tabs(["☢️ Fontes de Radiação", "🔋 Fontes de Referência",
                   "🔬 Conj. Dosimétricos", "📏 Instrumentos",
                   "🧊 Fantomas", "📡 Monitores de Área", "🖥️ Outros"])

    with sub[0]:
        sec("Equipamentos / Fontes Emissoras de Radiação Ionizante")
        tabela_editavel("equipamentos", [
            ("nome","Nome"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("serie","Nº Série"),("fabricacao","Fabricação"),("aceite","Aceite"),
            ("energia","Energia"),("radiacao","Radiação"),("taxa_dose","Taxa de Dose"),
        ])

    with sub[1]:
        sec("Fontes de Referência Seladas")
        tabela_editavel("fontes_referencia", [
            ("obj","Item"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("serie","Série"),("fabricacao","Fabricação"),
            ("atividade","Atividade"),("tipo","Tipo"),
        ])

    with sub[2]:
        sec("Conjuntos Dosimétricos (Câmaras e Eletrômetros)")
        tabela_editavel("conjunto_dosimetrico", [
            ("obj","Item"),("fabricante","Fabricante"),
            ("modelo","Modelo"),("serie","Nº Série"),
        ])

    with sub[3]:
        sec("Outros Instrumentos de Medição")
        tabela_editavel("instrumentos_medicao", [
            ("obj","Item"),("fabricante","Fabricante"),
            ("modelo","Modelo"),("serie","Nº Série"),
        ])

    with sub[4]:
        sec("Fantomas")
        tabela_editavel("fantomas", [
            ("obj","Item"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("dimensoes","Dimensões"),("material","Material"),
        ])

    with sub[5]:
        sec("Monitores de Área")
        tabela_editavel("monitores_area", [
            ("obj","Item"),("fabricante","Fabricante"),
            ("modelo","Modelo"),("serie","Nº Série"),
        ])

    with sub[6]:
        sec("Outros Detectores / Equipamentos")
        tabela_editavel("outros_detectores", [
            ("obj","Item"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("serie","Nº Série"),("data","Data"),("tipo","Tipo"),
        ])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 4 – GARANTIA DA QUALIDADE
# ───────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    sub = st.tabs(["📅 Diários", "📆 Mensais", "🗓️ Anuais",
                   "💉 Braquiterapia", "🔆 Ortovoltagem",
                   "🖥️ Sistemas de Planejamento", "🎯 Técnicas de Tratamento"])

    with sub[0]:
        sec("Testes Diários – Segurança, Dosimétricos e Mecânicos")
        tabela_editavel("testes_diarios",
            [("tipo","Tipo"),("teste","Teste"),("tolerancia","Tolerância")])

    with sub[1]:
        sec("Testes Mensais")
        tabela_editavel("testes_mensais",
            [("tipo","Tipo"),("teste","Teste"),("tolerancia","Tolerância")])

    with sub[2]:
        sec("Testes Anuais")
        tabela_editavel("testes_anuais",
            [("tipo","Tipo"),("teste","Teste"),("tolerancia","Tolerância")])

    with sub[3]:
        sec("Testes Diários – Braquiterapia")
        tabela_editavel("testes_diarios_braqui",
            [("teste","Teste"),("tolerancia","Tolerância")])
        sec("Testes Trimestrais – Braquiterapia")
        tabela_editavel("testes_trimestrais_braqui",
            [("teste","Teste"),("tolerancia","Tolerância")])

    with sub[4]:
        sec("Testes Mensais – Ortovoltagem")
        tabela_editavel("testes_mensais_orto",
            [("teste","Teste"),("tolerancia","Tolerância")])

    with sub[5]:
        sec("Sistemas de Planejamento")
        tabela_editavel("sistemas_planejamento",
            [("nome","Nome"),("fabricante","Fabricante"),
             ("versao","Versão"),("tecnicas","Técnicas")])

    with sub[6]:
        sec("Técnicas de Tratamento")
        tabela_editavel("tecnicas_tratamento",
            [("nome","Nome"),("descricao","Descrição")])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 5 – TEXTOS DOS CAPÍTULOS
# ───────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    tc = d.get("textos_caps", {})
    textos_conf = [
        ("classificacao_areas",    "Classificação de Áreas"),
        ("controle_acesso",        "Mecanismos de Controle de Acesso"),
        ("monitoracao_individual", "Monitoração Individual"),
        ("monitoracao_areas",      "Monitoração de Áreas"),
        ("controle_medico",        "Controle Médico dos IOEs"),
        ("niveis_operacionais",    "Níveis Operacionais e Restrições"),
        ("procedimentos_emergencia","Procedimentos de Emergência"),
        ("programa_treinamento",   "Programa de Treinamento em PR"),
        ("programa_educacao",      "Programa de Educação Continuada"),
        ("gerencia_rejeitos",      "Gerência de Rejeitos Radioativos"),
        ("calculo_barreiras",      "Cálculo de Barreiras"),
        ("matriz_risco",           "Matriz de Risco"),
        ("auditoria_externa",      "Auditoria Externa"),
    ]
    st.caption("💡 Textos importados do projeto aparecem pré-preenchidos. Edite conforme necessário.")
    for chave, label in textos_conf:
        preenchido = bool(tc.get(chave, "").strip())
        icone = "✅" if preenchido else "📄"
        with st.expander(f"{icone} {label}", expanded=not preenchido):
            tc[chave] = st.text_area(
                label, tc.get(chave, ""), height=200,
                key=f"tc_{chave}_{sv}",   # ← sv garante refresh após import
                label_visibility="collapsed"
            )
    d["textos_caps"] = tc


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 6 – ARQUIVOS PDFs
# ───────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    pdfs_importados = d.get("pdfs", {})
    pdfs_bytes_map  = d.get("_pdfs_bytes", {})

    # Conta arquivos por status
    total_vinculados = sum(len(v) for v in pdfs_importados.values() if isinstance(v, list))
    total_uploaded   = len(pdfs_bytes_map)

    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("📋 Caminhos vinculados", total_vinculados,
                     help="Arquivos referenciados no projeto original (caminhos locais)")
    col_info2.metric("⬆️ PDFs carregados", total_uploaded,
                     help="Arquivos efetivamente enviados nesta sessão e prontos para o PDF")
    col_info3.metric("⚠️ Pendentes de upload",
                     max(0, total_vinculados - total_uploaded),
                     help="Arquivos vinculados que ainda precisam ser enviados")

    st.info(
        "📎 **Como funciona:** O projeto original vinculava PDFs por caminho local (G:/...). "
        "Na versão web, você precisa **fazer upload** de cada arquivo. "
        "Os arquivos carregados ✅ serão incorporados ao PPR gerado."
    )
    st.divider()

    secoes_pdf = [
        ("autorizacao_funcionamento",         "Autorização de Funcionamento (CNEN)"),
        ("calculo_blindagem",                 "Cálculo de Blindagem"),
        ("levantamento_radiometrico",         "Levantamento Radiométrico"),
        ("classificacao_areas",               "Classificação de Áreas"),
        ("sevrra",                            "SEVRRA"),
        ("auditoria",                         "Auditoria Dosimétrica"),
        ("certificados_conjunto_dosimetrico", "Certificados – Conjuntos Dosimétricos"),
        ("certificados_monitores_area",       "Certificados – Monitores de Área"),
        ("certificados_outros",               "Certificados – Outros"),
        ("contrato_monitoracao",              "Contrato de Monitoração Individual"),
        ("procedimentos_emergencia",          "Procedimentos de Emergência"),
        ("gerencia_rejeitos",                 "Gerência de Rejeitos"),
    ]

    c1, c2 = st.columns(2)
    for i, (chave, label) in enumerate(secoes_pdf):
        col = c1 if i % 2 == 0 else c2
        with col:
            # Verifica status desta seção
            paths_vinculados = pdfs_importados.get(chave, [])
            paths_vinculados = [p for p in paths_vinculados if p]  # remove vazios
            uploaded_nesta_secao = [
                v["nome"] for v in pdfs_bytes_map.values()
                if v.get("chave_secao") == chave
            ]
            n_vinc = len(paths_vinculados)
            n_up   = len(uploaded_nesta_secao)

            if n_up > 0:
                icone = "✅"
            elif n_vinc > 0:
                icone = "⚠️"
            else:
                icone = "📁"

            status_txt = f"{n_up} carregado(s)" if n_up > 0 else (
                f"{n_vinc} vinculado(s) — upload pendente" if n_vinc > 0 else "vazio"
            )

            with st.expander(f"{icone} {label} — {status_txt}", expanded=(n_vinc > 0 and n_up == 0)):
                # Mostra caminhos originais importados
                if paths_vinculados:
                    st.markdown("**📋 Arquivos do projeto original:**")
                    for p in paths_vinculados:
                        nome_arquivo = p.replace("\\", "/").split("/")[-1]
                        st.caption(f"  📄 {nome_arquivo}")
                    st.markdown("**⬆️ Faça upload dos arquivos acima:**")

                upload_pdfs(chave, f"Selecionar PDF(s) – {label}")

    sec("Logo da Instituição")
    logo_up = st.file_uploader("Imagem do logo (PNG/JPG)", type=["png","jpg","jpeg"])
    if logo_up:
        d["_logo_bytes"] = base64.b64encode(logo_up.read()).decode()
        st.success("Logo carregado!")
    if d.get("_logo_bytes"):
        try:
            img_b = base64.b64decode(d["_logo_bytes"])
            st.image(img_b, width=200)
        except Exception:
            pass

    # Resumo de arquivos carregados
    if d.get("_pdfs_bytes"):
        sec("Arquivos Carregados na Sessão")
        por_secao: dict = {}
        for k, v in d["_pdfs_bytes"].items():
            sec_k = v.get("chave_secao","?")
            por_secao.setdefault(sec_k, []).append(v["nome"])
        for s, nomes in por_secao.items():
            st.write(f"**{s}:** " + ", ".join(nomes))

        if st.button("🗑️ Limpar todos os PDFs carregados"):
            d["_pdfs_bytes"] = {}
            st.rerun()


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 7 – GERAR PDF
# ───────────────────────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("📑 Geração do Plano de Proteção Radiológica")
    inst_v = d["instalacao"]

    # ── Checklist de validação ────────────────────────────────────────────────
    pct, itens = calcular_progresso(d)
    criticos_faltando = erros_criticos(itens)

    col_check, col_gerar = st.columns([3, 2])

    with col_check:
        sec("✅ Checklist de Completude")

        # Agrupa por categoria
        grupos = [
            ("🏥 Identificação",      itens[0:6]),
            ("👤 Responsáveis",       itens[6:11]),
            ("👥 Equipes",            itens[11:14]),
            ("⚙️ Equipamentos",       itens[14:17]),
            ("✅ Garantia Qualidade", itens[17:21]),
            ("📝 Textos",             itens[21:]),
        ]
        for titulo_grp, grupo in grupos:
            ok_grp = sum(1 for i in grupo if i["ok"])
            total_grp = len(grupo)
            cor_grp = "🟢" if ok_grp == total_grp else "🟡" if ok_grp > 0 else "🔴"
            with st.expander(f"{cor_grp} {titulo_grp} — {ok_grp}/{total_grp}", expanded=(ok_grp < total_grp)):
                for item in grupo:
                    icon = "✅" if item["ok"] else ("❌" if item["critico"] else "⚠️")
                    sufixo = " *(obrigatório)*" if item["critico"] and not item["ok"] else ""
                    st.markdown(f"{icon} {item['label']}{sufixo}")

    with col_gerar:
        sec("📊 Resumo")
        st.metric("Preenchimento", f"{pct}%")

        c1g, c2g = st.columns(2)
        c1g.metric("✅ OK", sum(1 for i in itens if i["ok"]))
        c2g.metric("❌ Faltando", len(itens) - sum(1 for i in itens if i["ok"]))

        if criticos_faltando:
            faltando_txt = "\n".join(f"- {i['label']}" for i in criticos_faltando)
            st.error(f"{len(criticos_faltando)} campo(s) obrigatório(s) faltando:\n{faltando_txt}")
        else:
            st.success("Todos os campos obrigatórios preenchidos! O PPR pode ser gerado.")





        st.divider()

        # Resumo rápido
        st.markdown("**Resumo do projeto:**")
        st.write(f"🏥 {inst_v.get('nome','—')}")
        st.write(f"📋 CNEN: {inst_v.get('matricula_cnen','—')}")
        st.write(f"📍 {inst_v.get('cidade','—')}/{inst_v.get('uf','—')}")
        st.write(f"👥 {len(d.get('equipes_medicos',[]))} médicos · "
                 f"{len(d.get('equipes_fisicos',[]))} físicos")
        st.write(f"⚙️ {len(d.get('equipamentos',[]))} equipamentos")
        st.write(f"📎 {len(d.get('_pdfs_bytes',{}))} PDFs anexados")

        st.divider()

        # Botão de geração — bloqueado se críticos faltando
        if criticos_faltando:
            st.warning("Complete os campos obrigatórios (❌) antes de gerar o PDF.")
            gerar_disabled = True
        else:
            gerar_disabled = False

        if st.button("📑 Gerar PDF", type="primary", width="stretch",
                     disabled=gerar_disabled):
            with st.spinner("Compilando o PPR... isso pode levar alguns segundos."):
                try:
                    from ppr_pdf_web import gerar_pdf_bytes
                    pdf_bytes = gerar_pdf_bytes(d)
                    nome_pdf = (inst_v.get("nome") or "PPR")[:30].replace(" ","_")
                    st.success("✅ PDF gerado com sucesso!")
                    st.download_button(
                        label="⬇️ Baixar PPR.pdf",
                        data=pdf_bytes,
                        file_name=f"PPR_{nome_pdf}.pdf",
                        mime="application/pdf",
                        width="stretch",
                    )
                except ImportError:
                    st.error("❌ Módulo ppr_pdf_web não encontrado.")
                except Exception as e:
                    st.error(f"❌ Erro ao gerar PDF: {e}")
                    st.exception(e)

        st.caption(
            "Os PDFs enviados na aba 'Arquivos PDFs' (SEVRRA, blindagem, auditoria etc.) "
            "serão incorporados automaticamente ao documento final."
        )
