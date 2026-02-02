import streamlit as st
import json
import os
import pandas as pd
from localization import LANGUAGES
from collections import defaultdict

# --- Internationalization ---
if 'lang' not in st.session_state:
    st.session_state.lang = 'zh'

def t(key):
    return LANGUAGES[st.session_state.lang].get(key, key)

# --- UI Functions ---
def get_font_css(language):
    font_families = {
        'zh': "'Meiryo UI', 'Microsoft YaHei UI', sans-serif",
        'ja': "'Meiryo UI', 'Yu Gothic UI', sans-serif",
        'en': "'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif"
    }
    font_family = font_families.get(language, font_families['en'])
    return f"<style>body {{ font-family: {font_family}; }}</style>"

# --- Data Logic ---
DATA_DIR = "data_json"
DATA_FILE = os.path.join(DATA_DIR, "skills.json")
PATHS_FILE = os.path.join(DATA_DIR, "paths.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_data():
    if not os.path.exists(DATA_FILE): return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return []

def load_defined_paths():
    if not os.path.exists(PATHS_FILE): return []
    with open(PATHS_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_defined_paths(paths):
    with open(PATHS_FILE, 'w', encoding='utf-8') as f:
        json.dump(paths, f, indent=4, ensure_ascii=False)

def calculate_urgency(skills):
    for s in skills:
        prio = int(s.get('priority', 1))
        prof = int(s.get('proficiency', 0))
        s['urgency_score'] = prio * (5 - prof)
    return sorted(skills, key=lambda x: x['urgency_score'], reverse=True)

def generate_tree_dot(skills, all_paths):
    """生成 Graphviz DOT 格式的树状图数据，并对齐层级"""
    dot = ['digraph G {']
    dot.append('  rankdir=LR;')
    dot.append('  node [fontname="sans-serif", shape=box, style="filled,rounded", fillcolor="#f0f2f6"];')
    
    edges = set()
    levels = defaultdict(set)
    root_node_label = "🧠 " + t("page_title")
    levels[0].add(f'"{root_node_label}"')

    # 1. 构建所有节点和边，并记录每个节点的层级
    for path in all_paths:
        parts = [p.strip() for p in path.split('.') if p.strip()]
        parent = root_node_label
        for i, part in enumerate(parts):
            edges.add(f'"{parent}" -> "{part}"')
            levels[i + 1].add(f'"{part}"')
            parent = part
            
    for s in skills:
        path = s.get('path', '')
        parts = [p.strip() for p in path.split('.') if p.strip()]
        parent = root_node_label
        if parts:
            parent = parts[-1]

        name = s['name'].replace('"', '\"')
        prof = int(s.get('proficiency', 0))
        prio = int(s.get('priority', 0))
        display_name = f"{name} {'*' * prio}"
        
        if prof == 0: color = "#e0e0e0"
        elif prof == 1: color = "#ffcccc"
        elif prof <= 3: color = "#fff4cc"
        else: color = "#ccffcc"
        
        leaf_id = f"skill_{s['name']}_{s.get('path','')}"
        dot.append(f'  "{leaf_id}" [label="{display_name}", shape=note, fillcolor="{color}"];')
        edges.add(f'"{parent}" -> "{leaf_id}"')
        levels[len(parts) + 1].add(f'"{leaf_id}"')

    # 2. 添加所有边
    for edge in sorted(list(edges)):
        dot.append(f'  {edge};')
    
    # 3. 添加层级对齐 (rank=same)
    for level, nodes in levels.items():
        if len(nodes) > 1:
            nodes_str = "; ".join(sorted(list(nodes)))
            dot.append(f'  {{ rank=same; {nodes_str} }}')

    dot.append('}')
    return "\n".join(dot)


def build_path_tree(paths):
    tree = {}
    for p in paths:
        parts = [part.strip() for part in p.split('.') if p.strip()]
        current = tree
        for part in parts:
            if part not in current: current[part] = {}
            current = current[part]
    return tree

def update_path_references(old_path, new_path, recursive=True):
    skills, updated_count = load_data(), 0
    for s in skills:
        p = s.get('path', '')
        if p == old_path:
            s['path'], updated_count = new_path, updated_count + 1
        elif recursive and p.startswith(old_path + '.'):
            s['path'] = new_path + p[len(old_path):]
            updated_count += 1
    save_data(skills)
    paths, new_paths, changed = load_defined_paths(), [], False
    for p in paths:
        if p == old_path: new_paths.append(new_path); changed = True
        elif recursive and p.startswith(old_path + '.'): new_paths.append(new_path + p[len(old_path):]); changed = True
        else: new_paths.append(p)
    if changed: save_defined_paths(sorted(list(set(new_paths))))
    return updated_count

# --- Main App ---
st.set_page_config(page_title=t("page_title"), layout="wide")
st.markdown(get_font_css(st.session_state.lang), unsafe_allow_html=True)

all_data = load_data()
defined_paths = load_defined_paths()
existing_skill_paths = [d.get('path', '') for d in all_data if d.get('path')]
all_paths = sorted(list(set(existing_skill_paths + defined_paths)))

# --- Top-Right Controls ---
_, col1, col2 = st.columns([0.6, 0.2, 0.2])

with col1:
    lang_map = {'zh': '中文', 'en': 'English', 'ja': '日本語'}
    selected_lang_label = st.selectbox(
        label=t("language"),
        options=lang_map.keys(),
        format_func=lambda x: lang_map[x],
        key="lang_selector_top",
        label_visibility="collapsed"
    )
    if st.session_state.lang != selected_lang_label:
        st.session_state.lang = selected_lang_label
        st.rerun()

with col2:
    page = st.radio(
        label=t("view_switcher"),
        options=[t("home_view"), t("manage_view")],
        key="view_switcher_top",
        horizontal=True,
        label_visibility="collapsed"
    )
    
with st.sidebar:
    st.title(t("nav_title"))
    st.markdown("---")

if page == t("home_view"):
    st.title(t("main_title"))
    st.markdown("---")
    with st.sidebar:
        if st.session_state.get("submit_success", False):
            st.session_state.input_name, st.session_state.input_memo, st.session_state.submit_success = "", "", False
        
        st.header(t("add_skill_header"))
        with st.container(border=True):
            st.markdown(f"##### {t('path_box_title')}")
            path_tree = build_path_tree(all_paths)
            l1_opts = sorted(list(path_tree.keys()))
            l1_sel = st.radio(t("cat_l1"), l1_opts, index=None, key="path_l1")
            final_path_parts = []
            if l1_sel:
                final_path_parts.append(l1_sel)
                l2_opts = sorted(list(path_tree[l1_sel].keys()))
                if l2_opts:
                    l2_sel = st.radio(t("cat_l2"), l2_opts, index=None, key="path_l2")
                    if l2_sel:
                        final_path_parts.append(l2_sel)
                        l3_opts = sorted(list(path_tree[l1_sel][l2_sel].keys()))
                        if l3_opts:
                            l3_sel = st.radio(t("cat_l3"), l3_opts, index=None, key="path_l3")
                            if l3_sel: final_path_parts.append(l3_sel)
            selected_path = ".".join(final_path_parts)
            st.caption(t("path_to_be_added_to").format(path=selected_path) if selected_path else t("path_prompt"))
        with st.container(border=True):
            st.markdown(f"##### {t('details_box_title')}")
            name = st.text_input(t("skill_name_label"), placeholder=t("skill_name_placeholder"), key="input_name")
            col1, col2 = st.columns(2)
            with col1:
                st.write(t("proficiency_label"))
                proficiency = st.radio("proficiency_radio", options=[5, 4, 3, 2, 1, 0], index=2, label_visibility="collapsed")
            with col2:
                st.write(t("priority_label"))
                priority = st.radio("priority_radio", options=[3, 2, 1], index=1, label_visibility="collapsed")
            memo = st.text_area(t("memo_label"), placeholder=t("memo_placeholder"), height=68, key="input_memo")
        if st.button(t("submit_button"), type="primary", use_container_width=True):
            if name and selected_path:
                current_data = load_data()
                current_data.append({"name": name, "path": selected_path, "proficiency": proficiency, "priority": priority, "memo": memo})
                save_data(current_data)
                st.success(t("success_skill_added").format(name=name))
                st.session_state.submit_success = True
                st.rerun()
            else: st.error(t("error_skill_name_empty") if not name else t("error_path_empty"))

    raw_skills = load_data()
    filtered_data = raw_skills
    skills = calculate_urgency(filtered_data)
    if skills:
        scope = t("top_tasks_global_scope")
        st.subheader(t("top_tasks_header").format(scope=scope))
        top_cols = st.columns(3)
        for i, skill in enumerate(skills[:min(3, len(skills))]):
            with top_cols[i]:
                st.metric(label=skill['name'], value=t("urgency_metric").format(score=skill['urgency_score']), delta=t("priority_metric").format(prio=skill['priority']), delta_color="inverse")
                st.caption(t("path_metric").format(path=skill['path']))
        st.markdown("---")
        st.subheader(t("panorama_header"))
        tab1, tab2 = st.tabs([t("tab_list"), t("tab_tree")])
        with tab1:
            df = pd.DataFrame(skills).sort_values(by=['path', 'urgency_score'], ascending=[True, False])
            if 'memo' not in df.columns: df['memo'] = ""
            df['path'] = df['path'].astype(str).str.replace('.', ' ➤ ', regex=False)
            df_display = df[['path', 'name', 'proficiency', 'priority', 'urgency_score', 'memo']].rename(columns={'name': t('col_name'), 'path': t('col_path'), 'proficiency': t('col_proficiency'), 'priority': t('col_priority'), 'urgency_score': t('col_urgency'), 'memo': t('col_memo')})
            df_display = df_display.reset_index(drop=True)
            edit_mode = st.toggle(t("edit_mode_toggle"), value=False)
            if edit_mode:
                edited_df = st.data_editor(df_display, hide_index=True, num_rows="dynamic", column_config={t('col_urgency'): st.column_config.NumberColumn(width="small", disabled=True), t('col_proficiency'): st.column_config.NumberColumn(width="small"), t('col_priority'): st.column_config.NumberColumn(width="small")})
                if st.button(t("save_changes_button")):
                    df_save = edited_df.rename(columns={t('col_name'): 'name', t('col_path'): 'path', t('col_proficiency'): 'proficiency', t('col_priority'): 'priority', t('col_memo'): 'memo'})
                    if df_save['name'].isnull().any() or (df_save['name'].astype(str).str.strip() == "").any(): st.error(t("error_empty_name_in_table")); st.stop()
                    df_save['path'] = df_save['path'].str.replace(' ➤ ', '.', regex=False)
                    if 'urgency_score' in df_save.columns: df_save = df_save.drop(columns=['urgency_score'])
                    save_data(df_save.to_dict('records')); st.success(t("success_data_updated")); st.rerun()
            else:
                def get_prof_color(val):
                    if val == 0: return 'background-color: #e0e0e0'
                    elif val == 1: return 'background-color: #ffcccc'
                    elif val <= 3: return 'background-color: #fff4cc'
                    else: return 'background-color: #ccffcc'
                def get_prio_color(val):
                    if val == 3: return 'background-color: #ffcccc'
                    elif val == 2: return 'background-color: #fff4cc'
                    else: return 'background-color: #ccffcc'
                st.dataframe(df_display.style.map(get_prof_color, subset=[t('col_proficiency')]).map(get_prio_color, subset=[t('col_priority')]), hide_index=True)
        with tab2:
            st.caption(t("tree_legend")); st.graphviz_chart(generate_tree_dot(skills, all_paths))
    else: st.info(t("empty_tree_info"))
elif page == t("manage_view"):
    st.title(t("manage_page_title"))
    st.info(t("manage_page_info"))
    with st.container(border=True):
        st.subheader(t("graph_header"))
        if all_data or all_paths:
            st.caption(t("tree_legend")); st.graphviz_chart(generate_tree_dot(all_data, all_paths))
        else: st.info(t("empty_graph_info"))
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader(t("add_path_header"))
            parent_options = [t("parent_top_level")] + all_paths
            selected_parent = st.selectbox(t("select_parent_step1"), parent_options, help=t("select_parent_help"))
            new_part = st.text_input(t("add_child_step2"), placeholder=t("add_child_placeholder"))
            if st.button(t("add_node_button"), type="primary", use_container_width=True):
                if new_part:
                    new_part = new_part.strip().replace(".", "_")
                    if not new_part: st.warning(t("error_name_empty"))
                    else:
                        new_path_def = f"{selected_parent}.{new_part}" if selected_parent != t("parent_top_level") else new_part
                        current_paths = load_defined_paths()
                        if new_path_def not in current_paths:
                            current_paths.append(new_path_def); save_defined_paths(sorted(list(set(current_paths))))
                            st.success(t("success_path_added").format(path=new_path_def)); st.rerun()
                        else: st.warning(t("warning_path_exists"))
                else: st.warning(t("error_path_input_empty"))
            with st.expander(t("manual_path_expander")):
                manual_path_def = st.text_input(t("manual_path_input"), key="manual_path_def_page")
                if st.button(t("manual_add_button"), key="manual_add"):
                    if manual_path_def:
                        current_paths = load_defined_paths()
                        if manual_path_def not in current_paths:
                            current_paths.append(manual_path_def); save_defined_paths(sorted(list(set(current_paths))))
                            st.success(t("success_path_added").format(path=manual_path_def)); st.rerun()
                        else: st.warning(t("warning_path_exists"))
                    else: st.warning(t("error_path_input_empty"))
    with col2:
        with st.container(border=True):
            st.subheader(t("edit_path_header"))
            if not all_paths: st.warning(t("info_path_not_in_presets"))
            else:
                path_to_edit = st.selectbox(t("select_path_to_edit"), all_paths, key="path_to_edit_selectbox")
                action = st.radio(t("action_type_label"), [t("action_rename"), t("action_delete")], horizontal=True, key="action_radio")
                if action == t("action_rename"):
                    new_path_name = st.text_input(t("rename_to_label"), value=path_to_edit)
                    recursive = st.checkbox(t("rename_recursive_checkbox"), value=True)
                    if st.button(t("rename_confirm_button"), use_container_width=True):
                        if new_path_name and new_path_name != path_to_edit:
                            count = update_path_references(path_to_edit, new_path_name, recursive)
                            st.success(t("success_path_updated").format(count=count)); st.rerun()
                        else: st.warning(t("warning_path_not_changed"))
                elif action == t("action_delete"):
                    st.warning(t("delete_warning").format(path=path_to_edit))
                    st.caption(t("delete_caption"))
                    if st.button(t("delete_confirm_button"), use_container_width=True, type="secondary"):
                        current_paths = load_defined_paths()
                        if path_to_edit in current_paths:
                            current_paths.remove(path_to_edit); save_defined_paths(current_paths)
                            st.success(t("success_path_removed").format(path=path_to_edit)); st.rerun()
                        else: st.info(t("info_path_not_in_presets"))
