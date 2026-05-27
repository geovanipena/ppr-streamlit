#!/usr/bin/env python3
"""PPR Dash — Plano de Proteção Radiológica (Plotly Dash)"""
from __future__ import annotations
import base64, hashlib, io, json, os, re, tempfile
from datetime import datetime, timedelta

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, ctx, ALL, no_update
from dash.exceptions import PreventUpdate
import pandas as pd

# ── Setup ─────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="PPR — Gerador",
    meta_tags=[{"name": "viewport", "content": "width=device-width,initial-scale=1"}],
)
server = app.server

# ── Data Model ────────────────────────────────────────────────────────────────
def dados_iniciais() -> dict:
    now = datetime.now()
    return {
        "instalacao": {
            "nome": "", "matricula_cnen": "", "cnpj": "", "rua": "",
            "complemento": "", "bairro": "", "cidade": "", "uf": "", "cep": "",
            "telefone": "", "horario": "", "objetivo": "", "grupo": "",
            "subgrupo": "", "instituicao": "",
            "cidade_data": "", "mes": str(now.month), "ano": str(now.year),
        },
        "responsaveis": [],
        "supervisor": {"nome": "", "rt": "", "ra": ""},
        "substituto_supervisor": {"nome": "", "rt": "", "ra": ""},
        "responsavel_tecnico": {"nome": "", "crm": "", "cb": ""},
        "substituto_rt": {"nome": "", "crm": "", "cb": ""},
        "diretor_clinico": {"nome": "", "crm": ""},
        "equipes_medicos": [], "equipes_fisicos": [], "equipes_tecnicos": [],
        "equipes_dosimetristas": [], "equipes_enfermagem": [], "equipes_demais": [],
        "asos": [],
        "equipamentos": [], "fontes_referencia": [], "conjunto_dosimetrico": [],
        "instrumentos_medicao": [], "fantomas": [], "monitores_area": [],
        "outros_detectores": [],
        "testes_diarios": [], "testes_mensais": [], "testes_anuais": [],
        "testes_diarios_braqui": [], "testes_trimestrais_braqui": [],
        "testes_mensais_orto": [],
        "sistemas_planejamento": [], "tecnicas_tratamento": [],
        "textos_caps": {
            "classificacao_areas": "", "controle_acesso": "",
            "monitoracao_individual": "", "monitoracao_areas": "",
            "controle_medico": "", "niveis_operacionais": "",
            "procedimentos_emergencia": "", "programa_treinamento": "",
            "programa_educacao": "", "gerencia_rejeitos": "",
            "calculo_barreiras": "", "matriz_risco": "", "auditoria_externa": "",
        },
        "pdfs": {},
        "vencimentos": {
            "autorizacao_funcionamento": {"realizacao": "", "vencimento": ""},
            "levantamento_radiometrico": {"realizacao": "", "vencimento": ""},
            "auditoria": {"realizacao": "", "vencimento": ""},
            "sevrra": {"realizacao": "", "vencimento": ""},
            "certificados_conjunto_dosimetrico": {"realizacao": "", "vencimento": ""},
            "certificados_outros": {"realizacao": "", "vencimento": ""},
            "certificados_monitores_area": {"realizacao": "", "vencimento": ""},
        },
        "imagens": {"logo": "", "classificacao_areas": [], "gerencia_rejeitos": []},
        "_pdfs_bytes": {}, "_logo_bytes": "",
    }


def calcular_progresso(d: dict) -> tuple[int, list]:
    checks = [
        ("nome instalação",      bool(d["instalacao"].get("nome")),              True),
        ("matrícula CNEN",       bool(d["instalacao"].get("matricula_cnen")),    True),
        ("CNPJ",                 bool(d["instalacao"].get("cnpj")),              True),
        ("grupo CNEN",           bool(d["instalacao"].get("grupo")),             True),
        ("titulares",            bool(d.get("responsaveis")),                    True),
        ("SPR nome",             bool(d["supervisor"].get("nome")),              True),
        ("SPR RT",               bool(d["supervisor"].get("rt")),                True),
        ("substituto SPR",       bool(d["substituto_supervisor"].get("nome")),   True),
        ("RT nome",              bool(d["responsavel_tecnico"].get("nome")),     True),
        ("RT CRM",               bool(d["responsavel_tecnico"].get("crm")),      True),
        ("médicos",              bool(d.get("equipes_medicos")),                 True),
        ("físicos",              bool(d.get("equipes_fisicos")),                 True),
        ("fontes/equip.",        bool(d.get("equipamentos") or d.get("fontes_referencia")), True),
        ("dosimétricos",         bool(d.get("conjunto_dosimetrico")),            True),
        ("testes diários",       bool(d.get("testes_diarios")),                 True),
        ("testes mensais",       bool(d.get("testes_mensais")),                 True),
        ("testes anuais",        bool(d.get("testes_anuais")),                  True),
        ("texto: classif.áreas", bool(d["textos_caps"].get("classificacao_areas")), True),
        ("texto: monit.indiv.",  bool(d["textos_caps"].get("monitoracao_individual")), True),
        ("texto: emergência",    bool(d["textos_caps"].get("procedimentos_emergencia")), True),
        ("endereço",             bool(d["instalacao"].get("rua") and d["instalacao"].get("cidade")), False),
        ("técnicos RT",          bool(d.get("equipes_tecnicos")),               False),
        ("ASOs",                 bool(d.get("asos")),                           False),
        ("sistemas planej.",     bool(d.get("sistemas_planejamento")),          False),
        ("PDFs anexados",        bool(d.get("_pdfs_bytes")),                    False),
        ("textos opcionais",     bool(d["textos_caps"].get("controle_acesso")), False),
    ]
    total = len(checks)
    done = sum(1 for _, ok, _ in checks if ok)
    pendentes = [(n, ok) for n, ok, crit in checks if crit and not ok]
    return int(done * 100 // total), pendentes


def dias_vencimento(s: str):
    if not s or len(s) < 8:
        return None
    try:
        d = datetime.strptime(s.strip(), "%d/%m/%Y")
        return (d - datetime.now()).days
    except ValueError:
        return None


def chip_status(dias):
    if dias is None:
        return html.Span("—", style=CHIP | {"background": "rgba(100,116,139,.15)", "color": "#94A3B8"})
    if dias < 0:
        return html.Span(f"Vencido {abs(dias)}d", style=CHIP | {"background": "rgba(239,68,68,.15)", "color": "#EF4444"})
    if dias <= 30:
        return html.Span(f"⚠ {dias}d", style=CHIP | {"background": "rgba(239,68,68,.15)", "color": "#EF4444"})
    if dias <= 90:
        return html.Span(f"⚠ {dias}d", style=CHIP | {"background": "rgba(245,158,11,.15)", "color": "#F59E0B"})
    return html.Span(f"✓ {dias}d", style=CHIP | {"background": "rgba(34,197,94,.15)", "color": "#22C55E"})


CHIP = {
    "display": "inline-block", "padding": "4px 12px",
    "borderRadius": "20px", "fontSize": "12px", "fontWeight": "600",
}

# ── Anthropic ─────────────────────────────────────────────────────────────────
def get_client():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except Exception:
        return None


# ── CSS ───────────────────────────────────────────────────────────────────────

# ── Component Helpers ─────────────────────────────────────────────────────────
def lbl(text, req=False):
    return html.Label([text, html.Span("*", style={"color": "#3B82F6", "marginLeft": "2px"}) if req else ""], className="field-label")

def inp(id, value="", placeholder="", type="text", debounce=True):
    return html.Div(dcc.Input(id=id, value=value, placeholder=placeholder, type=type,
                              debounce=debounce, className="ppr-input"),
                    className="ppr-input-wrap")

def textarea(id, value="", placeholder="", rows=4):
    return html.Div(dcc.Textarea(id=id, value=value, placeholder=placeholder,
                                 style={"minHeight": f"{rows*28}px"}),
                    className="ppr-textarea-wrap")

def field(label, component, req=False, col=12):
    return dbc.Col([lbl(label, req), component], width=col, className="mb-3")

def make_table(table_id, cols, data=None):
    columns = [{"name": c["name"], "id": c["id"], "editable": True, "deletable": False} for c in cols]
    return html.Div([
        dash_table.DataTable(
            id=table_id,
            columns=columns,
            data=data or [],
            editable=True,
            row_deletable=True,
            style_table={"overflowX": "auto"},
            style_cell={"backgroundColor": "rgba(255,255,255,.03)", "color": "#CBD5E1",
                        "border": "1px solid rgba(255,255,255,.06)", "padding": "9px 14px",
                        "fontFamily": "Inter,sans-serif", "fontSize": "13px"},
            style_header={"backgroundColor": "rgba(15,31,61,.95)", "color": "#64748B",
                          "border": "1px solid rgba(255,255,255,.07)", "fontWeight": "700",
                          "fontSize": "11px", "textTransform": "uppercase", "letterSpacing": ".07em",
                          "padding": "11px 14px"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,.01)"},
                {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,.12)",
                 "border": "1px solid rgba(59,130,246,.35)"},
            ],
        ),
        html.Button("+ Adicionar linha", id={"type": "add-row", "table": table_id},
                    className="btn-ppr btn-ghost mt-1"),
    ])

def card(children, cls=""):
    return html.Div(children, className=f"ppr-card {cls}")

def divider():
    return html.Hr(className="ppr-divider")

# ── Section Layouts ───────────────────────────────────────────────────────────

def section_instalacao(d: dict) -> html.Div:
    inst = d.get("instalacao", {})
    return html.Div([
        html.H2("🏥 Instalação", className="sec-title"),
        html.P("Dados de identificação e endereço da instalação", className="sec-sub"),

        card([
            html.P("Identificação", className="sub-title"),
            dbc.Row([
                field("Nome da Instituição", inp("inst-nome", inst.get("nome",""), "Ex.: Hospital do Câncer XYZ"), req=True, col=6),
                field("Matrícula CNEN", inp("inst-matricula", inst.get("matricula_cnen",""), "CNEN-XXX-XXXX"), req=True, col=3),
                field("CNPJ", inp("inst-cnpj", inst.get("cnpj",""), "00.000.000/0000-00"), req=True, col=3),
            ]),
            dbc.Row([
                field("Objetivo / Finalidade", textarea("inst-objetivo", inst.get("objetivo",""), "Descreva brevemente o objetivo da instalação..."), col=8),
                dbc.Col([
                    dbc.Row([field("Telefone", inp("inst-tel", inst.get("telefone",""), "(00) 0000-0000"), col=12)]),
                    dbc.Row([field("Horário de Funcionamento", inp("inst-horario", inst.get("horario",""), "Seg–Sex 07h–19h"), col=12)]),
                ], width=4),
            ]),
        ]),

        card([
            html.P("Endereço", className="sub-title"),
            dbc.Row([
                field("Rua / Av.", inp("inst-rua", inst.get("rua",""), "Ex.: Rua das Acácias"), req=True, col=6),
                field("Complemento / Nº", inp("inst-compl", inst.get("complemento",""), "Sala 101"), col=3),
                field("Bairro", inp("inst-bairro", inst.get("bairro",""), "Centro"), col=3),
            ]),
            dbc.Row([
                field("Cidade", inp("inst-cidade", inst.get("cidade",""), "São Paulo"), req=True, col=5),
                field("UF", inp("inst-uf", inst.get("uf",""), "SP"), req=True, col=2),
                field("CEP", inp("inst-cep", inst.get("cep",""), "00000-000"), req=True, col=3),
                field("Grupo CNEN", inp("inst-grupo", inst.get("grupo",""), "Grupo A"), req=True, col=2),
            ]),
            dbc.Row([
                field("Subgrupo", inp("inst-subgrupo", inst.get("subgrupo",""), "Subgrupo 1"), col=4),
                field("Cabeçalho (Instituição)", inp("inst-inst", inst.get("instituicao",""), "Nome para cabeçalho do PDF"), col=8),
            ]),
        ]),

        card([
            html.P("Data do Documento", className="sub-title"),
            dbc.Row([
                field("Cidade (para data)", inp("inst-cidade-data", inst.get("cidade_data",""), "São Paulo"), col=6),
                field("Mês", inp("inst-mes", inst.get("mes",""), "1–12"), col=3),
                field("Ano", inp("inst-ano", inst.get("ano",""), "2025"), col=3),
            ]),
        ]),

        dbc.Row([
            dbc.Col(html.Button("💾 Salvar Instalação", id="save-instalacao",
                                className="btn-ppr btn-blue"), width="auto"),
            dbc.Col(html.Div(id="msg-instalacao"), width="auto", className="d-flex align-items-center"),
        ], className="mt-2"),
    ])


def section_pessoal(d: dict) -> html.Div:
    sv = d.get("supervisor", {})
    ss = d.get("substituto_supervisor", {})
    rt = d.get("responsavel_tecnico", {})
    sr = d.get("substituto_rt", {})
    dc = d.get("diretor_clinico", {})

    def person_block(title, name_id, nv, f2_lbl, f2_id, f2_v, f3_lbl, f3_id, f3_v):
        return html.Div([
            html.P(title, className="sub-title mt-2"),
            dbc.Row([
                field("Nome", inp(name_id, nv, "Nome completo"), req=True, col=6),
                field(f2_lbl, inp(f2_id, f2_v), req=True, col=3),
                field(f3_lbl, inp(f3_id, f3_v), col=3),
            ]),
        ])

    cols_resp = [{"name": "Nome", "id": "nome"}, {"name": "CPF", "id": "cpf"}, {"name": "Cargo", "id": "cargo"}]
    cols_med = [{"name": "Nome", "id": "nome"}, {"name": "CRM", "id": "crm"}, {"name": "CB", "id": "cb"},
                {"name": "Venc. CB", "id": "venc_cb"}, {"name": "Carga Hor.", "id": "carga"}]
    cols_fis = [{"name": "Nome", "id": "nome"}, {"name": "RT", "id": "rt"}, {"name": "Venc. RT", "id": "venc_rt"},
                {"name": "RA", "id": "ra"}, {"name": "Venc. RA", "id": "venc_ra"},
                {"name": "Formação", "id": "formacao"}, {"name": "Carga Hor.", "id": "carga"}]
    cols_tec = [{"name": "Nome", "id": "nome"}, {"name": "CRTR", "id": "crtr"}, {"name": "Carga Hor.", "id": "carga"}]
    cols_dos = [{"name": "Nome", "id": "nome"}, {"name": "Registro", "id": "registro"}, {"name": "Carga Hor.", "id": "carga"}]
    cols_enf = [{"name": "Nome", "id": "nome"}, {"name": "COREN", "id": "coren"}, {"name": "Carga Hor.", "id": "carga"}]
    cols_dem = [{"name": "Nome", "id": "nome"}, {"name": "Cargo", "id": "cargo"}, {"name": "Carga Hor.", "id": "carga"}]
    cols_aso = [{"name": "Nome do IOE", "id": "nome"}, {"name": "Último ASO", "id": "ultimo"}, {"name": "Validade", "id": "validade"}]

    return html.Div([
        html.H2("👥 Pessoal", className="sec-title"),
        html.P("Equipes e responsáveis pela instalação", className="sec-sub"),

        dbc.Tabs([
            dbc.Tab(card([
                html.P("Titulares / Responsáveis pelo CNEN", className="sub-title"),
                make_table("tbl-responsaveis", cols_resp, d.get("responsaveis", [])),
                divider(),
                person_block("Supervisor de Radioproteção (SPR)", "spr-nome", sv.get("nome",""),
                             "Nº RT CNEN", "spr-rt", sv.get("rt",""), "Nº RA CNEN", "spr-ra", sv.get("ra","")),
                person_block("Substituto do SPR", "sspr-nome", ss.get("nome",""),
                             "Nº RT CNEN", "sspr-rt", ss.get("rt",""), "Nº RA CNEN", "sspr-ra", ss.get("ra","")),
                divider(),
                person_block("Responsável Técnico (RT)", "rt-nome", rt.get("nome",""),
                             "CRM", "rt-crm", rt.get("crm",""), "CB", "rt-cb", rt.get("cb","")),
                person_block("Substituto do RT", "srt-nome", sr.get("nome",""),
                             "CRM", "srt-crm", sr.get("crm",""), "CB", "srt-cb", sr.get("cb","")),
                divider(),
                html.P("Diretor Clínico", className="sub-title"),
                dbc.Row([
                    field("Nome", inp("dc-nome", dc.get("nome","")), col=6),
                    field("CRM", inp("dc-crm", dc.get("crm","")), col=3),
                ]),
                dbc.Row([dbc.Col(html.Button("💾 Salvar Pessoal", id="save-pessoal", className="btn-ppr btn-blue"), width="auto"),
                         dbc.Col(html.Div(id="msg-pessoal"), width="auto", className="d-flex align-items-center")]),
            ]), label="👤 Responsáveis", tab_id="resp"),

            dbc.Tab(card([
                html.P("Radio-Oncologistas", className="sub-title"),
                make_table("tbl-medicos", cols_med, d.get("equipes_medicos", [])),
            ]), label="👨‍⚕️ Médicos", tab_id="med"),

            dbc.Tab(card([
                html.P("Físicos Médicos", className="sub-title"),
                make_table("tbl-fisicos", cols_fis, d.get("equipes_fisicos", [])),
            ]), label="🔬 Físicos", tab_id="fis"),

            dbc.Tab(card([
                html.P("Técnicos em Radioterapia", className="sub-title"),
                make_table("tbl-tecnicos", cols_tec, d.get("equipes_tecnicos", [])),
            ]), label="🛠️ Técnicos", tab_id="tec"),

            dbc.Tab(card([
                html.P("Dosimetristas", className="sub-title"),
                make_table("tbl-dosimetristas", cols_dos, d.get("equipes_dosimetristas", [])),
            ]), label="📐 Dosimetristas", tab_id="dos"),

            dbc.Tab(card([
                html.P("Equipe de Enfermagem", className="sub-title"),
                make_table("tbl-enfermagem", cols_enf, d.get("equipes_enfermagem", [])),
            ]), label="🩺 Enfermagem", tab_id="enf"),

            dbc.Tab(card([
                html.P("Demais IOEs", className="sub-title"),
                make_table("tbl-demais", cols_dem, d.get("equipes_demais", [])),
            ]), label="👥 Demais IOEs", tab_id="dem"),

            dbc.Tab(card([
                html.P("ASOs — Atestados de Saúde Ocupacional", className="sub-title"),
                make_table("tbl-asos", cols_aso, d.get("asos", [])),
                divider(),
                html.P("Extração automática por IA", className="sub-title"),
                dcc.Upload(id="upload-asos-pdf",
                    children=html.Div([html.Div("📄", className="upload-icon"),
                                       html.Div([html.Strong("Clique ou arraste o PDF com ASOs"), html.Span(" (PDF com todos os ASOs consolidados)", className="text-muted")], className="upload-text")]),
                    className="ppr-upload", multiple=False, accept=".pdf"),
                html.Div(id="msg-asos-upload", className="mt-2"),
                dbc.Row([
                    dbc.Col(html.Button("🤖 Extrair e preencher tabela", id="btn-extrair-asos",
                                       className="btn-ppr btn-blue mt-2"), width="auto"),
                ]),
                html.Div(id="msg-asos-extrai", className="mt-2"),
            ]), label="🏥 ASOs", tab_id="aso"),
        ], id="tabs-pessoal", active_tab="resp", className="ppr-tabs"),
    ])


def section_equipamentos(d: dict) -> html.Div:
    cols_equip = [{"name": "Nome/Modelo", "id": "nome"}, {"name": "Fabricante", "id": "fabricante"},
                  {"name": "Modelo", "id": "modelo"}, {"name": "Série", "id": "serie"},
                  {"name": "Fab.", "id": "fabricacao"}, {"name": "Aceite", "id": "aceite"},
                  {"name": "Energia", "id": "energia"}, {"name": "Radiação", "id": "radiacao"},
                  {"name": "Taxa Dose", "id": "taxa_dose"}]
    cols_fonte = [{"name": "Objeto", "id": "obj"}, {"name": "Fabricante", "id": "fabricante"},
                  {"name": "Modelo", "id": "modelo"}, {"name": "Série", "id": "serie"},
                  {"name": "Fabricação", "id": "fabricacao"}, {"name": "Atividade", "id": "atividade"},
                  {"name": "Tipo", "id": "tipo"}]
    cols_dosim = [{"name": "Objeto", "id": "obj"}, {"name": "Fabricante", "id": "fabricante"},
                  {"name": "Modelo", "id": "modelo"}, {"name": "Série", "id": "serie"},
                  {"name": "Calibração", "id": "calibracao"}, {"name": "Fator", "id": "fator"}]
    cols_instr = [{"name": "Objeto", "id": "obj"}, {"name": "Fabricante", "id": "fabricante"},
                  {"name": "Modelo", "id": "modelo"}, {"name": "Série", "id": "serie"},
                  {"name": "Calibração", "id": "calibracao"}]
    cols_fant  = [{"name": "Objeto", "id": "obj"}, {"name": "Fabricante", "id": "fabricante"},
                  {"name": "Modelo", "id": "modelo"}, {"name": "Dimensões", "id": "dimensoes"},
                  {"name": "Material", "id": "material"}]
    cols_mon   = cols_dosim[:]
    cols_out   = [{"name": "Objeto", "id": "obj"}, {"name": "Fabricante", "id": "fabricante"},
                  {"name": "Modelo", "id": "modelo"}, {"name": "Série", "id": "serie"},
                  {"name": "Data", "id": "data"}, {"name": "Tipo", "id": "tipo"}]

    return html.Div([
        html.H2("⚙️ Equipamentos", className="sec-title"),
        html.P("Fontes de radiação, dosímetros e instrumentos de medição", className="sec-sub"),
        dbc.Tabs([
            dbc.Tab(card([html.P("Fontes de Radiação (Aceleradores, Tomoterapia, Gammaknife...)", className="sub-title"),
                          make_table("tbl-equipamentos", cols_equip, d.get("equipamentos",[]))]),
                    label="☢️ Fontes Radiação", tab_id="eq1"),
            dbc.Tab(card([html.P("Fontes de Referência", className="sub-title"),
                          make_table("tbl-fontes-ref", cols_fonte, d.get("fontes_referencia",[]))]),
                    label="🔋 Fontes Referência", tab_id="eq2"),
            dbc.Tab(card([html.P("Conjuntos Dosimétricos (câmara + eletrômetro)", className="sub-title"),
                          make_table("tbl-conj-dosim", cols_dosim, d.get("conjunto_dosimetrico",[]))]),
                    label="🔬 Conj. Dosimétricos", tab_id="eq3"),
            dbc.Tab(card([html.P("Instrumentos de Medição", className="sub-title"),
                          make_table("tbl-instrumentos", cols_instr, d.get("instrumentos_medicao",[]))]),
                    label="📏 Instrumentos", tab_id="eq4"),
            dbc.Tab(card([html.P("Fantomas", className="sub-title"),
                          make_table("tbl-fantomas", cols_fant, d.get("fantomas",[]))]),
                    label="🧊 Fantomas", tab_id="eq5"),
            dbc.Tab(card([html.P("Monitores de Área", className="sub-title"),
                          make_table("tbl-monitores", cols_mon, d.get("monitores_area",[]))]),
                    label="📡 Monitores Área", tab_id="eq6"),
            dbc.Tab(card([html.P("Outros Detectores / Equipamentos", className="sub-title"),
                          make_table("tbl-outros-det", cols_out, d.get("outros_detectores",[]))]),
                    label="🖥️ Outros", tab_id="eq7"),
        ], id="tabs-equip", active_tab="eq1", className="ppr-tabs"),
    ])


def section_qualidade(d: dict) -> html.Div:
    cols_teste3 = [{"name": "Tipo", "id": "tipo"}, {"name": "Teste", "id": "teste"}, {"name": "Tolerância", "id": "tolerancia"}]
    cols_teste2 = [{"name": "Teste", "id": "teste"}, {"name": "Tolerância", "id": "tolerancia"}]
    cols_sist   = [{"name": "Nome", "id": "nome"}, {"name": "Fabricante", "id": "fabricante"},
                   {"name": "Versão", "id": "versao"}, {"name": "Técnicas", "id": "tecnicas"}]
    cols_tec    = [{"name": "Técnica", "id": "nome"}, {"name": "Descrição", "id": "descricao"}]

    return html.Div([
        html.H2("✅ Garantia da Qualidade", className="sec-title"),
        html.P("Protocolos de testes por modalidade", className="sec-sub"),
        dbc.Tabs([
            dbc.Tab(card([
                html.P("Aceleradores Lineares — Testes Diários", className="sub-title"),
                make_table("tbl-t-diarios", cols_teste3, d.get("testes_diarios",[])),
                divider(),
                html.P("Testes Mensais", className="sub-title"),
                make_table("tbl-t-mensais", cols_teste3, d.get("testes_mensais",[])),
                divider(),
                html.P("Testes Anuais", className="sub-title"),
                make_table("tbl-t-anuais", cols_teste3, d.get("testes_anuais",[])),
            ]), label="🔬 Aceleradores Lineares", tab_id="qa1"),

            dbc.Tab(card([
                html.P("Braquiterapia — Testes Diários", className="sub-title"),
                make_table("tbl-t-braqui-d", cols_teste2, d.get("testes_diarios_braqui",[])),
                divider(),
                html.P("Testes Trimestrais", className="sub-title"),
                make_table("tbl-t-braqui-t", cols_teste2, d.get("testes_trimestrais_braqui",[])),
            ]), label="💉 Braquiterapia", tab_id="qa2"),

            dbc.Tab(card([
                html.P("Ortovoltagem — Testes Mensais", className="sub-title"),
                make_table("tbl-t-orto", cols_teste2, d.get("testes_mensais_orto",[])),
            ]), label="🔆 Ortovoltagem", tab_id="qa3"),

            dbc.Tab(card([
                html.P("Sistemas de Planejamento (TPS)", className="sub-title"),
                make_table("tbl-sistemas", cols_sist, d.get("sistemas_planejamento",[])),
            ]), label="🖥️ Sist. Planejamento", tab_id="qa4"),

            dbc.Tab(card([
                html.P("Técnicas de Tratamento", className="sub-title"),
                make_table("tbl-tecnicas", cols_tec, d.get("tecnicas_tratamento",[])),
            ]), label="🎯 Técnicas", tab_id="qa5"),
        ], id="tabs-qa", active_tab="qa1", className="ppr-tabs"),
    ])


def section_textos(d: dict) -> html.Div:
    tc = d.get("textos_caps", {})
    TEXTOS = [
        ("classificacao_areas",     "5. Classificação de Áreas",             True),
        ("controle_acesso",         "6. Controle de Acesso",                 False),
        ("monitoracao_individual",  "7. Monitoração Individual",             True),
        ("monitoracao_areas",       "8. Monitoração de Áreas",               False),
        ("controle_medico",         "9. Controle Médico dos IOEs",           False),
        ("niveis_operacionais",     "10. Níveis Operacionais e Restrições",  False),
        ("procedimentos_emergencia","11. Procedimentos de Emergência",       True),
        ("programa_treinamento",    "12. Programa de Treinamento em PR",     False),
        ("programa_educacao",       "13. Programa de Educação Continuada",   False),
        ("gerencia_rejeitos",       "14. Gerência de Rejeitos Radioativos",  False),
        ("calculo_barreiras",       "15. Cálculo de Barreiras",              False),
        ("matriz_risco",            "16. Matriz de Risco",                   False),
        ("auditoria_externa",       "17. Auditoria Externa",                 False),
    ]
    items = []
    for key, title, req in TEXTOS:
        val = tc.get(key, "")
        ico = "✅" if val else ("🔴" if req else "📄")
        items.append(
            dbc.AccordionItem([
                textarea(f"txt-{key}", val, f"Insira o texto do capítulo '{title}'...", rows=8),
            ], title=f"{ico}  {title}", item_id=key)
        )

    return html.Div([
        html.H2("📝 Textos", className="sec-title"),
        html.P("Conteúdo narrativo dos capítulos do PPR", className="sec-sub"),
        html.Div(className="alert-info mb-3",
                 children="💡 Textos marcados com 🔴 são obrigatórios para gerar o PDF. Itens com ✅ já estão preenchidos."),
        card([
            dbc.Accordion(items, start_collapsed=True, always_open=True, id="accord-textos"),
            dbc.Row([
                dbc.Col(html.Button("💾 Salvar Textos", id="save-textos", className="btn-ppr btn-blue mt-3"), width="auto"),
                dbc.Col(html.Div(id="msg-textos"), width="auto", className="d-flex align-items-center mt-3"),
            ]),
        ]),
    ])


def section_arquivos(d: dict) -> html.Div:
    pdfs_bytes = d.get("_pdfs_bytes", {})
    SECOES = [
        ("autorizacao_funcionamento", "Autorização de Funcionamento (CNEN)", True, ".pdf"),
        ("calculo_blindagem",         "Cálculo de Blindagem",                True, ".pdf"),
        ("levantamento_radiometrico", "Levantamento Radiométrico",           False, ".pdf"),
        ("classificacao_areas",       "Classificação de Áreas",              False, ".pdf,.png,.jpg,.jpeg"),
        ("sevrra",                    "SEVRRA",                              True,  ".pdf"),
        ("auditoria",                 "Auditoria Dosimétrica",               False, ".pdf"),
        ("certificados_conjunto_dosimetrico", "Certificados — Conj. Dosimétricos", False, ".pdf"),
        ("certificados_monitores_area",       "Certificados — Monitores de Área",  False, ".pdf"),
        ("certificados_outros",       "Certificados — Outros",               False, ".pdf"),
        ("contrato_monitoracao",      "Contrato de Monitoração Individual",  False, ".pdf"),
        ("procedimentos_emergencia",  "Procedimentos de Emergência",         False, ".pdf,.png,.jpg,.jpeg"),
        ("gerencia_rejeitos",         "Gerência de Rejeitos",                False, ".pdf,.png,.jpg,.jpeg"),
    ]

    def upload_section(key, title, req, accept):
        uploads_for_key = {k: v for k, v in pdfs_bytes.items() if v.get("chave_secao") == key}
        badge = "🔴" if req else "📎"
        status_items = []
        for fname, finfo in uploads_for_key.items():
            status_items.append(html.Div([
                html.Span("✅", style={"marginRight": "6px", "color": "#22C55E"}),
                html.Span(finfo.get("nome", fname), style={"fontSize": "12px", "color": "#CBD5E1"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}))

        return dbc.AccordionItem([
            dcc.Upload(
                id={"type": "upload-pdf", "key": key},
                children=html.Div([
                    html.Div("📄", className="upload-icon"),
                    html.Div([html.Strong("Clique ou arraste"), html.Span(f" ({accept})", className="text-muted")], className="upload-text"),
                ]),
                className="ppr-upload", multiple=True, accept=accept,
            ),
            html.Div(status_items or [html.Span("Nenhum arquivo carregado", className="text-muted fs-12 mt-1")],
                     id={"type": "upload-pdf-status", "key": key}, className="mt-2"),
        ], title=f"{badge}  {title}", item_id=key)

    sections_left  = [upload_section(k, t, r, a) for k, t, r, a in SECOES[:6]]
    sections_right = [upload_section(k, t, r, a) for k, t, r, a in SECOES[6:]]

    n_loaded = len(pdfs_bytes)
    logo_b64 = d.get("_logo_bytes", "")

    return html.Div([
        html.H2("🗂️ Arquivos", className="sec-title"),
        html.P("PDFs, imagens e documentos que serão incorporados ao PPR", className="sec-sub"),

        dbc.Row([
            dbc.Col(html.Div([html.Div(str(n_loaded), className="metric-val"), html.Div("Arquivos Carregados", className="metric-lbl")], className="metric-card"), width=3),
            dbc.Col(html.Div([html.Div("3", className="metric-val"), html.Div("Obrigatórios", className="metric-lbl")], className="metric-card"), width=3),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col([card([
                html.P("Documentos (1/2)", className="sub-title"),
                dbc.Accordion(sections_left, start_collapsed=True, always_open=True),
            ])], width=6),
            dbc.Col([card([
                html.P("Documentos (2/2)", className="sub-title"),
                dbc.Accordion(sections_right, start_collapsed=True, always_open=True),
            ])], width=6),
        ]),

        card([
            html.P("Logo da Instituição", className="sub-title"),
            dbc.Row([
                dbc.Col([
                    dcc.Upload(id="upload-logo",
                               children=html.Div([html.Div("🏥", className="upload-icon"),
                                                  html.Div([html.Strong("Logo PNG/JPG"), html.Span(" (aparece na capa do PDF)", className="text-muted")], className="upload-text")]),
                               className="ppr-upload", multiple=False, accept=".png,.jpg,.jpeg"),
                ], width=6),
                dbc.Col(html.Div(id="logo-preview",
                                 children=html.Img(src=f"data:image/png;base64,{logo_b64}", style={"maxHeight": "80px", "borderRadius": "8px"}) if logo_b64 else html.Span("Nenhum logo carregado", className="text-muted fs-12")),
                        width=6, className="d-flex align-items-center"),
            ]),
        ]),
    ])


def section_vencimentos(d: dict) -> html.Div:
    venc = d.get("vencimentos", {})
    DOCS = [
        ("autorizacao_funcionamento",       "Autorização de Funcionamento"),
        ("levantamento_radiometrico",       "Levantamento Radiométrico"),
        ("auditoria",                       "Auditoria Dosimétrica"),
        ("sevrra",                          "SEVRRA"),
        ("certificados_conjunto_dosimetrico","Cert. Conj. Dosimétricos"),
        ("certificados_outros",             "Cert. Outros"),
        ("certificados_monitores_area",     "Cert. Monitores de Área"),
    ]

    table_rows = []
    for key, title in DOCS:
        v = venc.get(key, {})
        dias = dias_vencimento(v.get("vencimento",""))
        table_rows.append(html.Tr([
            html.Td(title, style={"fontSize": "13px", "color": "#CBD5E1", "padding": "10px 14px"}),
            html.Td(dcc.Input(id=f"venc-real-{key}", value=v.get("realizacao",""),
                              placeholder="DD/MM/AAAA", debounce=True,
                              style={"background": "rgba(255,255,255,.06)", "border": "1px solid rgba(255,255,255,.1)",
                                     "borderRadius": "7px", "color": "#E2E8F0", "padding": "7px 12px",
                                     "fontSize": "13px", "width": "140px"}),
                    style={"padding": "10px 14px"}),
            html.Td(dcc.Input(id=f"venc-venc-{key}", value=v.get("vencimento",""),
                              placeholder="DD/MM/AAAA", debounce=True,
                              style={"background": "rgba(255,255,255,.06)", "border": "1px solid rgba(255,255,255,.1)",
                                     "borderRadius": "7px", "color": "#E2E8F0", "padding": "7px 12px",
                                     "fontSize": "13px", "width": "140px"}),
                    style={"padding": "10px 14px"}),
            html.Td(chip_status(dias), style={"padding": "10px 14px"}),
        ]))

    asos = d.get("asos", [])
    aso_rows_parsed = []
    for a in asos:
        dias = dias_vencimento(a.get("validade",""))
        aso_rows_parsed.append((a.get("nome",""), a.get("ultimo",""), a.get("validade",""), dias))
    aso_rows_parsed.sort(key=lambda x: x[3] if x[3] is not None else 9999)
    aso_rows = [html.Tr([
        html.Td(n, style={"fontSize": "13px", "color": "#CBD5E1", "padding": "9px 14px"}),
        html.Td(u, style={"fontSize": "13px", "color": "#94A3B8", "padding": "9px 14px"}),
        html.Td(v, style={"fontSize": "13px", "color": "#94A3B8", "padding": "9px 14px"}),
        html.Td(chip_status(dias), style={"padding": "9px 14px"}),
    ]) for n, u, v, dias in aso_rows_parsed[:10]]

    return html.Div([
        html.H2("📅 Vencimentos", className="sec-title"),
        html.P("Controle de validades de documentos e ASOs", className="sec-sub"),

        dbc.Row([
            dbc.Col(html.Button("🤖 Extrair datas dos PDFs carregados", id="btn-extrair-venc",
                                className="btn-ppr btn-blue"), width="auto"),
            dbc.Col(html.Div(id="msg-venc-extrai"), width="auto", className="d-flex align-items-center"),
        ], className="mb-3"),

        card([
            html.P("Documentos Principais", className="sub-title"),
            html.Div(html.Table([
                html.Thead(html.Tr([
                    html.Th("Documento", style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px",
                                                "textTransform": "uppercase", "letterSpacing": ".07em",
                                                "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                    html.Th("Realização", style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px",
                                                 "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                    html.Th("Vencimento", style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px",
                                                 "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                    html.Th("Status", style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px",
                                             "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                ])),
                html.Tbody(table_rows),
            ], style={"width": "100%", "borderCollapse": "collapse", "borderRadius": "12px", "overflow": "hidden"})),

            dbc.Row([
                dbc.Col(html.Button("💾 Salvar Vencimentos", id="save-vencimentos", className="btn-ppr btn-blue mt-3"), width="auto"),
                dbc.Col(html.Div(id="msg-vencimentos"), width="auto", className="d-flex align-items-center mt-3"),
            ]),
        ]),

        card([
            html.P(f"ASOs — Próximos Vencimentos (top {min(10, len(aso_rows_parsed))})", className="sub-title"),
            html.Div(html.Table([
                html.Thead(html.Tr([
                    html.Th("IOE",       style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px", "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                    html.Th("Último ASO",style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px", "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                    html.Th("Validade",  style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px", "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                    html.Th("Status",    style={"padding": "11px 14px", "color": "#64748B", "fontSize": "11px", "textTransform": "uppercase", "background": "rgba(15,31,61,.95)", "fontWeight": "700"}),
                ])),
                html.Tbody(aso_rows if aso_rows else [html.Tr(html.Td("Nenhum ASO cadastrado", colSpan=4, style={"textAlign": "center", "padding": "20px", "color": "#475569", "fontSize": "13px"}))]),
            ], style={"width": "100%", "borderCollapse": "collapse"})) if True else html.Div("Nenhum ASO cadastrado", className="text-muted fs-13"),
        ]),
    ])


def section_gerar(d: dict) -> html.Div:
    pct, pendentes = calcular_progresso(d)

    if pct >= 80:
        pct_color = "#22C55E"
        pct_cls   = "alert-success"
        pct_msg   = "✅ Projeto completo — pronto para gerar o PDF!"
    elif pct >= 50:
        pct_color = "#F59E0B"
        pct_cls   = "alert-warning"
        pct_msg   = f"⚠ {len(pendentes)} itens críticos pendentes"
    else:
        pct_color = "#EF4444"
        pct_cls   = "alert-danger"
        pct_msg   = f"🔴 {len(pendentes)} itens críticos faltando"

    CHECKLIST = [
        ("🏥 Identificação",   ["nome instalação", "matrícula CNEN", "CNPJ", "grupo CNEN"]),
        ("👤 Responsáveis",    ["titulares", "SPR nome", "SPR RT", "substituto SPR"]),
        ("👥 Equipes",         ["médicos", "físicos"]),
        ("⚙️ Equipamentos",    ["fontes/equip.", "dosimétricos"]),
        ("✅ Testes QA",        ["testes diários", "testes mensais", "testes anuais"]),
        ("📝 Textos",          ["texto: classif.áreas", "texto: monit.indiv.", "texto: emergência"]),
    ]
    pend_set = {n for n, _ in pendentes}
    check_items = []
    for group, items in CHECKLIST:
        check_items.append(html.Div(group, className="sub-title mt-3"))
        for item in items:
            ok = item not in pend_set
            check_items.append(html.Div([
                html.Span("✅" if ok else "❌", className="check-ok" if ok else "check-fail"),
                html.Span(item, style={"fontSize": "13px", "marginLeft": "8px"}),
            ], className="check-item"))

    inst = d.get("instalacao", {})
    disabled = len(pendentes) > 0

    return html.Div([
        html.H2("📑 Gerar PDF", className="sec-title"),
        html.P("Revisão final e exportação do Plano de Proteção Radiológica", className="sec-sub"),

        dbc.Row([
            dbc.Col([
                card([
                    html.P("✅ Checklist de Completude", className="sub-title"),
                    html.Div(check_items),
                ]),
            ], width=7),

            dbc.Col([
                card([
                    html.P("📊 Status do Projeto", className="sub-title"),
                    dbc.Row([
                        dbc.Col(html.Div([html.Div(f"{pct}%", className="metric-val", style={"color": pct_color}),
                                         html.Div("Preenchimento", className="metric-lbl")], className="metric-card"), width=6),
                        dbc.Col(html.Div([html.Div(str(26 - len(pendentes)), className="metric-val", style={"color": "#22C55E"}),
                                         html.Div("Concluídos", className="metric-lbl")], className="metric-card"), width=6),
                    ], className="mb-3"),

                    html.Div(pct_msg, className=pct_cls + " mb-3"),

                    html.Div([
                        html.Div([html.Span("Instituição: ", className="text-muted fs-12"), html.Span(inst.get("nome","—"), style={"fontSize": "13px"})]),
                        html.Div([html.Span("CNEN: ", className="text-muted fs-12"), html.Span(inst.get("matricula_cnen","—"), style={"fontSize": "13px"})]),
                        html.Div([html.Span("Cidade/UF: ", className="text-muted fs-12"), html.Span(f"{inst.get('cidade','—')}/{inst.get('uf','—')}", style={"fontSize": "13px"})]),
                    ], className="ppr-card-accent mb-3"),
                ]),

                card([
                    html.P("Exportação", className="sub-title"),
                    html.Button(
                        "📑 Gerar PDF", id="btn-gerar-pdf",
                        className="btn-ppr btn-blue w-100 mb-2",
                        disabled=disabled,
                        style={"opacity": ".5" if disabled else "1"},
                    ),
                    html.Div(id="msg-gerar-pdf", className="mb-2"),
                    dcc.Loading(html.Div(id="download-pdf-wrap"), type="circle", color="#3B82F6"),
                    html.Button("⬇️ Baixar JSON do Projeto", id="btn-baixar-json",
                                className="btn-ppr btn-outline w-100 mt-2"),
                ]),
            ], width=5),
        ]),
    ])


def section_onboarding() -> html.Div:
    return html.Div([
        html.Div([
            html.Div("☢️", style={"fontSize": "64px", "marginBottom": "16px"}),
            html.H1("Gerador de PPR", style={"fontSize": "32px", "fontWeight": "800", "color": "#F1F5F9", "marginBottom": "8px"}),
            html.P("Plano de Proteção Radiológica — Radioterapia", style={"color": "#475569", "marginBottom": "48px", "fontSize": "16px"}),
        ], style={"textAlign": "center"}),

        dbc.Row([
            dbc.Col(html.Div([
                html.Div("🆕", style={"fontSize": "40px", "marginBottom": "16px"}),
                html.H3("Novo Projeto", style={"color": "#E2E8F0", "fontWeight": "700", "marginBottom": "8px"}),
                html.P("Comece um PPR do zero", style={"color": "#64748B", "fontSize": "13px"}),
                dcc.Link("Começar", href="/instalacao",
                         className="btn-ppr btn-blue mt-3",
                         style={"display": "inline-block", "textDecoration": "none"}),
            ], className="onboard-card"), width=5),

            dbc.Col(html.Div([
                html.Div("📂", style={"fontSize": "40px", "marginBottom": "16px"}),
                html.H3("Carregar Projeto", style={"color": "#E2E8F0", "fontWeight": "700", "marginBottom": "8px"}),
                html.P("Importar JSON salvo anteriormente", style={"color": "#64748B", "fontSize": "13px"}),
                dcc.Upload(id="upload-projeto",
                           children=html.Button("Selecionar arquivo", className="btn-ppr btn-outline mt-3"),
                           multiple=False, accept=".json,.txt"),
            ], className="onboard-card"), width=5),
        ], justify="center", className="mt-2"),
        html.Div(id="msg-onboard", className="mt-3", style={"textAlign": "center"}),
    ], style={"maxWidth": "700px", "margin": "80px auto", "padding": "0 24px"})


# ── Sidebar ───────────────────────────────────────────────────────────────────
def build_sidebar(d: dict, active: str) -> html.Div:
    pct, pendentes = calcular_progresso(d)
    if pct >= 80: fill_color = "#22C55E"
    elif pct >= 50: fill_color = "#F59E0B"
    else: fill_color = "#EF4444"

    nav_items = []
    for key, icon, label in [
        ("instalacao",   "🏥", "Instalação"),
        ("pessoal",      "👥", "Pessoal"),
        ("equipamentos", "⚙️", "Equipamentos"),
        ("qualidade",    "✅", "Garantia Qualidade"),
        ("textos",       "📝", "Textos"),
        ("arquivos",     "🗂️", "Arquivos"),
        ("vencimentos",  "📅", "Vencimentos"),
        ("gerar",        "📑", "Gerar PDF"),
    ]:
        is_active = key == active
        nav_items.append(
            dcc.Link([
                html.Span(icon, className="nav-pill-icon"),
                html.Span(label, className="nav-pill-text"),
            ], href=f"/{key}",
               className=f"nav-pill {'active' if is_active else ''}",
               style={"textDecoration": "none"})
        )

    inst_nome = d.get("instalacao", {}).get("nome", "") or "Novo Projeto"

    return html.Div([
        html.Div([
            html.Div("☢️ PPR Gerador", className="sidebar-logo-title"),
            html.Div("Plano de Proteção Radiológica", className="sidebar-logo-sub"),
        ], className="sidebar-logo"),

        html.Div([
            html.Div([
                html.Div([
                    html.Div(f"{pct}%", className="progress-ring-pct", style={"color": fill_color}),
                    html.Div([
                        html.Div("Completado", className="progress-ring-label"),
                        html.Div(inst_nome[:20] + ("…" if len(inst_nome) > 20 else ""), style={"fontSize": "12px", "color": "#4A6A9A", "marginTop": "2px"}),
                    ]),
                ], className="progress-ring-wrap"),
            ]),
            html.Div([
                html.Div(style={"width": f"{pct}%", "height": "100%", "background": fill_color, "borderRadius": "2px", "transition": "width .4s ease"}),
            ], className="sidebar-progress-bar"),
        ], className="sidebar-progress-wrap"),

        html.Div(nav_items, className="sidebar-nav"),

        html.Div([
            # Visual button — uses clientside JS to click the hidden static btn-sidebar-save
            html.Button("⬇️ Salvar Projeto (JSON)", id="btn-sidebar-save-visual",
                        className="btn-ppr btn-outline w-100", n_clicks=0,
                        style={"fontSize": "12px", "padding": "8px 12px"}),
        ], className="sidebar-bottom"),
    ], className="ppr-sidebar")


# ── App Layout ────────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="dados", storage_type="session", data=None),

    # Static downloads (always in DOM so callbacks can write to them)
    dcc.Download(id="dl-sidebar-json"),
    dcc.Download(id="dl-json"),
    dcc.Download(id="dl-pdf"),

    # Sidebar
    html.Div(id="sidebar-wrap"),

    # Main
    html.Div([
        html.Div(id="ppr-header-wrap"),
        html.Div(id="page-content", className="ppr-content"),
    ], id="ppr-main", className="ppr-main"),
])


# ── Callbacks ─────────────────────────────────────────────────────────────────

# Render page — URL-based routing (dcc.Link handles navigation client-side)
@app.callback(
    Output("page-content", "children"),
    Output("sidebar-wrap", "children"),
    Output("ppr-header-wrap", "children"),
    Output("ppr-main", "style"),
    Output("dados", "data", allow_duplicate=True),
    Input("url", "pathname"),
    State("dados", "data"),
    prevent_initial_call="initial_duplicate",
)
def render_page(pathname, dados):
    section = (pathname or "/").lstrip("/") or "onboarding"
    SECTIONS = {"instalacao","pessoal","equipamentos","qualidade","textos","arquivos","vencimentos","gerar"}

    is_onboard = section not in SECTIONS

    if is_onboard:
        return section_onboarding(), None, None, {"marginLeft": "0"}, no_update

    # Initialize dados if navigating fresh (no data yet)
    if dados is None:
        dados = dados_iniciais()
        init_dados = dados
    else:
        init_dados = no_update

    d = dados
    sidebar = build_sidebar(d, section)
    header = html.Div([
        html.Div([
            html.Div("Plano de Proteção Radiológica", className="header-title"),
            html.Div(d.get("instalacao",{}).get("nome","") or "Sem nome", className="header-inst"),
        ]),
        html.Div([
            html.Span(f"Matrícula: {d.get('instalacao',{}).get('matricula_cnen','—')}", className="text-muted fs-12 me-3"),
        ]),
    ], className="ppr-header")

    section_fns = {
        "instalacao": section_instalacao,
        "pessoal": section_pessoal,
        "equipamentos": section_equipamentos,
        "qualidade": section_qualidade,
        "textos": section_textos,
        "arquivos": section_arquivos,
        "vencimentos": section_vencimentos,
        "gerar": section_gerar,
    }
    fn = section_fns.get(section, section_instalacao)
    content = fn(d)
    return content, sidebar, header, {"marginLeft": "240px"}, init_dados


# Onboarding: load project from file
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("url", "pathname"),
    Output("msg-onboard", "children"),
    Input("upload-projeto", "contents"),
    State("upload-projeto", "filename"),
    prevent_initial_call=True,
)
def load_projeto(contents, filename):
    if not contents:
        raise PreventUpdate
    try:
        _, encoded = contents.split(",", 1)
        raw = base64.b64decode(encoded).decode("utf-8")
        loaded = json.loads(raw)
        di = dados_iniciais()
        di.update({k: v for k, v in loaded.items() if k in di})
        return di, "/instalacao", no_update
    except Exception as e:
        return no_update, no_update, html.Div(f"❌ Erro ao carregar: {e}", className="alert-danger")


# Save instalacao
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("msg-instalacao", "children"),
    Input("save-instalacao", "n_clicks"),
    State("dados", "data"),
    State("inst-nome", "value"),
    State("inst-matricula", "value"),
    State("inst-cnpj", "value"),
    State("inst-objetivo", "value"),
    State("inst-tel", "value"),
    State("inst-horario", "value"),
    State("inst-rua", "value"),
    State("inst-compl", "value"),
    State("inst-bairro", "value"),
    State("inst-cidade", "value"),
    State("inst-uf", "value"),
    State("inst-cep", "value"),
    State("inst-grupo", "value"),
    State("inst-subgrupo", "value"),
    State("inst-inst", "value"),
    State("inst-cidade-data", "value"),
    State("inst-mes", "value"),
    State("inst-ano", "value"),
    prevent_initial_call=True,
)
def save_instalacao(n, dados, nome, matricula, cnpj, objetivo, tel, horario,
                    rua, compl, bairro, cidade, uf, cep, grupo, subgrupo,
                    inst, cidade_data, mes, ano):
    if not n:
        raise PreventUpdate
    d = dados if dados else dados_iniciais()
    d["instalacao"].update({
        "nome": nome or "", "matricula_cnen": matricula or "", "cnpj": cnpj or "",
        "objetivo": objetivo or "", "telefone": tel or "", "horario": horario or "",
        "rua": rua or "", "complemento": compl or "", "bairro": bairro or "",
        "cidade": cidade or "", "uf": uf or "", "cep": cep or "",
        "grupo": grupo or "", "subgrupo": subgrupo or "", "instituicao": inst or "",
        "cidade_data": cidade_data or "", "mes": mes or "", "ano": ano or "",
    })
    return d, html.Span("✅ Salvo!", style={"color": "#22C55E", "fontSize": "13px", "marginLeft": "8px"})


# Save pessoal (responsáveis + key persons)
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("msg-pessoal", "children"),
    Input("save-pessoal", "n_clicks"),
    State("dados", "data"),
    State("tbl-responsaveis", "data"),
    State("spr-nome", "value"), State("spr-rt", "value"), State("spr-ra", "value"),
    State("sspr-nome", "value"), State("sspr-rt", "value"), State("sspr-ra", "value"),
    State("rt-nome", "value"), State("rt-crm", "value"), State("rt-cb", "value"),
    State("srt-nome", "value"), State("srt-crm", "value"), State("srt-cb", "value"),
    State("dc-nome", "value"), State("dc-crm", "value"),
    prevent_initial_call=True,
)
def save_pessoal(n, dados, resp_rows, spr_n, spr_rt, spr_ra, sspr_n, sspr_rt, sspr_ra,
                 rt_n, rt_crm, rt_cb, srt_n, srt_crm, srt_cb, dc_n, dc_crm):
    if not n:
        raise PreventUpdate
    d = dados if dados else dados_iniciais()
    d["responsaveis"] = [r for r in (resp_rows or []) if any(str(v).strip() for v in r.values())]
    d["supervisor"] = {"nome": spr_n or "", "rt": spr_rt or "", "ra": spr_ra or ""}
    d["substituto_supervisor"] = {"nome": sspr_n or "", "rt": sspr_rt or "", "ra": sspr_ra or ""}
    d["responsavel_tecnico"] = {"nome": rt_n or "", "crm": rt_crm or "", "cb": rt_cb or ""}
    d["substituto_rt"] = {"nome": srt_n or "", "crm": srt_crm or "", "cb": srt_cb or ""}
    d["diretor_clinico"] = {"nome": dc_n or "", "crm": dc_crm or ""}
    return d, html.Span("✅ Salvo!", style={"color": "#22C55E", "fontSize": "13px", "marginLeft": "8px"})


# Save all tables via DataTable data changes
TABLE_MAP = {
    "tbl-medicos":       "equipes_medicos",
    "tbl-fisicos":       "equipes_fisicos",
    "tbl-tecnicos":      "equipes_tecnicos",
    "tbl-dosimetristas": "equipes_dosimetristas",
    "tbl-enfermagem":    "equipes_enfermagem",
    "tbl-demais":        "equipes_demais",
    "tbl-asos":          "asos",
    "tbl-equipamentos":  "equipamentos",
    "tbl-fontes-ref":    "fontes_referencia",
    "tbl-conj-dosim":    "conjunto_dosimetrico",
    "tbl-instrumentos":  "instrumentos_medicao",
    "tbl-fantomas":      "fantomas",
    "tbl-monitores":     "monitores_area",
    "tbl-outros-det":    "outros_detectores",
    "tbl-t-diarios":     "testes_diarios",
    "tbl-t-mensais":     "testes_mensais",
    "tbl-t-anuais":      "testes_anuais",
    "tbl-t-braqui-d":    "testes_diarios_braqui",
    "tbl-t-braqui-t":    "testes_trimestrais_braqui",
    "tbl-t-orto":        "testes_mensais_orto",
    "tbl-sistemas":      "sistemas_planejamento",
    "tbl-tecnicas":      "tecnicas_tratamento",
}

for _tbl_id, _data_key in TABLE_MAP.items():
    @app.callback(
        Output("dados", "data", allow_duplicate=True),
        Input(_tbl_id, "data"),
        State("dados", "data"),
        prevent_initial_call=True,
    )
    def save_table(rows, dados, _key=_data_key):
        d = dados if dados else dados_iniciais()
        d[_key] = [r for r in (rows or []) if any(str(v).strip() for v in r.values())]
        return d


# Add row pattern matching callback
@app.callback(
    Output({"type": "add-row", "table": ALL}, "n_clicks"),
    Input({"type": "add-row", "table": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def _reset_add_btns(clicks):
    return [0] * len(clicks)


# Each table add-row button — we need individual callbacks
def make_add_row_callback(tbl_id):
    @app.callback(
        Output(tbl_id, "data", allow_duplicate=True),
        Input({"type": "add-row", "table": tbl_id}, "n_clicks"),
        State(tbl_id, "data"),
        State(tbl_id, "columns"),
        prevent_initial_call=True,
    )
    def add_row(n, rows, cols):
        if not n:
            raise PreventUpdate
        rows = rows or []
        empty = {c["id"]: "" for c in (cols or [])}
        return rows + [empty]
    return add_row


for _tbl in list(TABLE_MAP.keys()) + ["tbl-responsaveis"]:
    make_add_row_callback(_tbl)


# Save textos
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("msg-textos", "children"),
    Input("save-textos", "n_clicks"),
    State("dados", "data"),
    State("txt-classificacao_areas", "value"),
    State("txt-controle_acesso", "value"),
    State("txt-monitoracao_individual", "value"),
    State("txt-monitoracao_areas", "value"),
    State("txt-controle_medico", "value"),
    State("txt-niveis_operacionais", "value"),
    State("txt-procedimentos_emergencia", "value"),
    State("txt-programa_treinamento", "value"),
    State("txt-programa_educacao", "value"),
    State("txt-gerencia_rejeitos", "value"),
    State("txt-calculo_barreiras", "value"),
    State("txt-matriz_risco", "value"),
    State("txt-auditoria_externa", "value"),
    prevent_initial_call=True,
)
def save_textos(n, dados, *vals):
    if not n:
        raise PreventUpdate
    keys = ["classificacao_areas", "controle_acesso", "monitoracao_individual",
            "monitoracao_areas", "controle_medico", "niveis_operacionais",
            "procedimentos_emergencia", "programa_treinamento", "programa_educacao",
            "gerencia_rejeitos", "calculo_barreiras", "matriz_risco", "auditoria_externa"]
    d = dados if dados else dados_iniciais()
    for k, v in zip(keys, vals):
        d["textos_caps"][k] = v or ""
    return d, html.Span("✅ Salvo!", style={"color": "#22C55E", "fontSize": "13px", "marginLeft": "8px"})


# File uploads
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Input({"type": "upload-pdf", "key": ALL}, "contents"),
    State({"type": "upload-pdf", "key": ALL}, "filename"),
    State({"type": "upload-pdf", "key": ALL}, "id"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def save_uploaded_pdfs(all_contents, all_filenames, all_ids, dados):
    d = dados if dados else dados_iniciais()
    pdfs = d.get("_pdfs_bytes", {})
    changed = False
    for contents_list, filenames_list, id_obj in zip(all_contents, all_filenames, all_ids):
        if not contents_list:
            continue
        key = id_obj["key"]
        if isinstance(contents_list, str):
            contents_list = [contents_list]
            filenames_list = [filenames_list] if isinstance(filenames_list, str) else filenames_list or ["arquivo.pdf"]
        for cont, fname in zip(contents_list, filenames_list or []):
            _, encoded = cont.split(",", 1)
            store_key = f"{key}__{fname}"
            pdfs[store_key] = {"nome": fname, "data": encoded, "chave_secao": key}
            changed = True
    if changed:
        d["_pdfs_bytes"] = pdfs
        return d
    raise PreventUpdate


# Logo upload
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("logo-preview", "children"),
    Input("upload-logo", "contents"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def save_logo(contents, dados):
    if not contents:
        raise PreventUpdate
    d = dados if dados else dados_iniciais()
    _, encoded = contents.split(",", 1)
    d["_logo_bytes"] = encoded
    img = html.Img(src=contents, style={"maxHeight": "80px", "borderRadius": "8px"})
    return d, img


# ASO upload (just store, extraction is separate)
@app.callback(
    Output("msg-asos-upload", "children"),
    Input("upload-asos-pdf", "filename"),
    prevent_initial_call=True,
)
def show_aso_upload(fname):
    if fname:
        return html.Div(f"✅ Arquivo selecionado: {fname}", className="alert-success")
    raise PreventUpdate


# ASO AI extraction
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("msg-asos-extrai", "children"),
    Input("btn-extrair-asos", "n_clicks"),
    State("upload-asos-pdf", "contents"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def extrair_asos(n, contents, dados):
    if not n or not contents:
        raise PreventUpdate
    client = get_client()
    if not client:
        return no_update, html.Div("❌ ANTHROPIC_API_KEY não configurada", className="alert-danger")
    try:
        import anthropic
        _, encoded = contents.split(",", 1)
        pdf_bytes = base64.b64decode(encoded)
        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": encoded}},
                    {"type": "text", "text": "Analise este documento e extraia os registros de ASO (Atestado de Saúde Ocupacional). Retorne APENAS um JSON válido com a lista: [{\"nome\": \"Nome Completo\", \"ultimo\": \"DD/MM/AAAA\", \"validade\": \"DD/MM/AAAA\"}, ...]. Sem texto adicional."}
                ]
            }]
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            extracted = json.loads(m.group())
        else:
            extracted = json.loads(text)
        d = dados if dados else dados_iniciais()
        existing = {a["nome"]: a for a in d.get("asos", [])}
        for item in extracted:
            if item.get("nome"):
                existing[item["nome"]] = item
        d["asos"] = list(existing.values())
        return d, html.Div(f"✅ {len(extracted)} ASO(s) extraído(s) com sucesso!", className="alert-success")
    except Exception as e:
        return no_update, html.Div(f"❌ Erro: {e}", className="alert-danger")


# Save vencimentos
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("msg-vencimentos", "children"),
    Input("save-vencimentos", "n_clicks"),
    State("dados", "data"),
    *[State(f"venc-real-{k}", "value") for k in [
        "autorizacao_funcionamento","levantamento_radiometrico","auditoria",
        "sevrra","certificados_conjunto_dosimetrico","certificados_outros","certificados_monitores_area"]],
    *[State(f"venc-venc-{k}", "value") for k in [
        "autorizacao_funcionamento","levantamento_radiometrico","auditoria",
        "sevrra","certificados_conjunto_dosimetrico","certificados_outros","certificados_monitores_area"]],
    prevent_initial_call=True,
)
def save_vencimentos(n, dados, *vals):
    if not n:
        raise PreventUpdate
    KEYS = ["autorizacao_funcionamento","levantamento_radiometrico","auditoria",
            "sevrra","certificados_conjunto_dosimetrico","certificados_outros","certificados_monitores_area"]
    reals = list(vals[:7])
    vencs = list(vals[7:])
    d = dados if dados else dados_iniciais()
    for k, r, v in zip(KEYS, reals, vencs):
        d["vencimentos"][k] = {"realizacao": r or "", "vencimento": v or ""}
    return d, html.Span("✅ Salvo!", style={"color": "#22C55E", "fontSize": "13px", "marginLeft": "8px"})


# Extract vencimentos via AI
@app.callback(
    Output("dados", "data", allow_duplicate=True),
    Output("msg-venc-extrai", "children"),
    Input("btn-extrair-venc", "n_clicks"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def extrair_vencimentos(n, dados):
    if not n:
        raise PreventUpdate
    d = dados if dados else dados_iniciais()
    pdfs_bytes = d.get("_pdfs_bytes", {})
    if not pdfs_bytes:
        return no_update, html.Div("⚠ Nenhum PDF carregado na aba Arquivos", className="alert-warning")
    client = get_client()
    if not client:
        return no_update, html.Div("❌ ANTHROPIC_API_KEY não configurada", className="alert-danger")

    KEYS = ["autorizacao_funcionamento","levantamento_radiometrico","auditoria",
            "sevrra","certificados_conjunto_dosimetrico","certificados_outros","certificados_monitores_area"]
    extracted_count = 0
    try:
        for store_key, finfo in pdfs_bytes.items():
            sec = finfo.get("chave_secao","")
            if sec not in KEYS:
                continue
            encoded = finfo.get("data","")
            if not encoded:
                continue
            resp = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": encoded}},
                        {"type": "text", "text": "Extraia a data de realização/emissão e a data de vencimento/validade deste documento. Responda SOMENTE JSON: {\"realizacao\": \"DD/MM/AAAA\", \"vencimento\": \"DD/MM/AAAA\"}. Se não encontrar, use string vazia."}
                    ]
                }]
            )
            text = resp.content[0].text.strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                result = json.loads(m.group())
                d["vencimentos"][sec] = {"realizacao": result.get("realizacao",""), "vencimento": result.get("vencimento","")}
                extracted_count += 1
        return d, html.Div(f"✅ {extracted_count} documento(s) analisado(s)", className="alert-success")
    except Exception as e:
        return d, html.Div(f"❌ Erro: {e}", className="alert-danger")


# Generate PDF
@app.callback(
    Output("download-pdf-wrap", "children"),
    Output("msg-gerar-pdf", "children"),
    Input("btn-gerar-pdf", "n_clicks"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def gerar_pdf(n, dados):
    if not n:
        raise PreventUpdate
    if not dados:
        return no_update, html.Div("❌ Nenhum dado encontrado", className="alert-danger")
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from ppr_pdf_web import gerar_pdf_bytes
        pdf_bytes = gerar_pdf_bytes(dados)
        inst = dados.get("instalacao", {})
        nome = (inst.get("nome") or "PPR").replace(" ", "_")[:30]
        filename = f"PPR_{nome}_{datetime.now().strftime('%Y%m%d')}.pdf"
        dl = dcc.Download(id="dl-pdf-gen",
                          data={"base64": True, "content": base64.b64encode(pdf_bytes).decode(), "filename": filename, "type": "application/pdf"})
        btn = html.Button("⬇️ Baixar PDF Gerado", id="btn-dl-pdf-gen", className="btn-ppr btn-green w-100")
        return html.Div([dl, btn]), html.Div("✅ PDF gerado com sucesso!", className="alert-success")
    except Exception as e:
        return no_update, html.Div(f"❌ Erro ao gerar PDF: {e}", className="alert-danger")


# Download JSON from sidebar
@app.callback(
    Output("dl-sidebar-json", "data"),
    Input("btn-sidebar-save-visual", "n_clicks"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def baixar_json_sidebar(n, dados):
    if not n or not dados:
        raise PreventUpdate
    export = {k: v for k, v in dados.items() if not k.startswith("_")}
    inst = dados.get("instalacao", {})
    nome = (inst.get("nome") or "PPR").replace(" ", "_")[:30]
    fname = f"PPR_{nome}_{datetime.now().strftime('%Y%m%d')}.json"
    return {"content": json.dumps(export, ensure_ascii=False, indent=2), "filename": fname}


# Download JSON from gerar page
@app.callback(
    Output("dl-json", "data"),
    Input("btn-baixar-json", "n_clicks"),
    State("dados", "data"),
    prevent_initial_call=True,
)
def baixar_json_gerar(n, dados):
    if not n or not dados:
        raise PreventUpdate
    export = {k: v for k, v in dados.items() if not k.startswith("_")}
    inst = dados.get("instalacao", {})
    nome = (inst.get("nome") or "PPR").replace(" ", "_")[:30]
    fname = f"PPR_{nome}_{datetime.now().strftime('%Y%m%d')}.json"
    return {"content": json.dumps(export, ensure_ascii=False, indent=2), "filename": fname}


# ── Server ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
