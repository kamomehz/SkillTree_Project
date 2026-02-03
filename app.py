import streamlit as st
import json
import os
import pandas as pd
from localization import LANGUAGES
from collections import defaultdict

# command to run the app:
# streamlit run app.py

# --- Internationalization ---
if 'lang' not in st.session_state:
    st.session_state.lang = 'zh'

def t(key, default=None):
    fallback = default if default is not None else key
    return LANGUAGES[st.session_state.lang].get(key, fallback)

# --- UI Functions ---
def get_font_css(language):
    font_families = {
        'zh': "'Meiryo UI', 'Microsoft YaHei UI', sans-serif",
        'ja': "'Meiryo UI', 'Yu Gothic UI', sans-serif",
        'en': "'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif"
    }
    font_family = font_families.get(language, font_families['en'])
    return f"<style>body {{ font-family: {font_family}; }}</style>"

def get_proficiency_color(prof):
    if prof == 0: return "#e0e0e0"
    if prof == 1: return "#ffcccc"
    if prof <= 3: return "#fff4cc"
    return "#ccffcc"

def get_priority_color(prio):
    if prio == 1: return "#d4edda"
    if prio == 2: return "#fff3cd"
    return "#f8d7da"

def color_box(value, color):
    return f"""
    <div style="background-color:{color}; padding:5px; border-radius:5px; text-align:center; margin:0; color: #333;">
        {value}
    </div>
    """

# --- Data Logic ---
DB_ROOT = "databases"
PROFILE_PREFIX = "skill_tree_"
PROFILE_SUFFIX = ".json"

def is_valid_profilename(name):
    """Checks if a string can be part of a valid filename for a profile."""
    if not name or name.isspace():
        return False, "Profile name cannot be empty."
    # Prohibit characters that are invalid in Windows/Linux filenames
    if any(char in '\\/:*?"<>|' for char in name):
        return False, "Profile name contains invalid characters (e.g., \\ / : * ? \" < > |)."
    if name in [".", ".."]:
        return False, "Profile name cannot be '.' or '..'."
    return True, ""

def migrate_old_profiles():
    """One-time migration from folder-based to file-based profiles."""
    if not os.path.exists(DB_ROOT):
        return

    migrated = False
    for item in os.listdir(DB_ROOT):
        item_path = os.path.join(DB_ROOT, item)
        if os.path.isdir(item_path):
            old_skill_tree_file = os.path.join(item_path, "skill_tree.json")
            if os.path.exists(old_skill_tree_file):
                profile_name = item
                new_file_path = os.path.join(DB_ROOT, f"{PROFILE_PREFIX}{profile_name}{PROFILE_SUFFIX}")

                if not os.path.exists(new_file_path):
                    import shutil
                    shutil.move(old_skill_tree_file, new_file_path)
                    migrated = True
                
                try:
                    # Cleanup old files and remove directory
                    old_skills = os.path.join(item_path, "skills.json")
                    old_paths = os.path.join(item_path, "paths.json")
                    if os.path.exists(old_skills): os.remove(old_skills)
                    if os.path.exists(old_paths): os.remove(old_paths)
                    os.rmdir(item_path)
                except OSError:
                    pass # Directory might not be empty, ignore in that case.
    if migrated and 'migration_success_shown' not in st.session_state:
        st.success("Successfully migrated old profiles to new file structure!")
        st.session_state.migration_success_shown = True

def get_profile_file_path(profile_name):
    return os.path.join(DB_ROOT, f"{PROFILE_PREFIX}{profile_name}{PROFILE_SUFFIX}")

def get_profiles():
    if not os.path.exists(DB_ROOT):
        os.makedirs(DB_ROOT)
    
    profiles = []
    for f in os.listdir(DB_ROOT):
        if f.startswith(PROFILE_PREFIX) and f.endswith(PROFILE_SUFFIX) and os.path.isfile(os.path.join(DB_ROOT, f)):
            profile_name = f[len(PROFILE_PREFIX):-len(PROFILE_SUFFIX)]
            if profile_name:
                profiles.append(profile_name)

    if "default" not in profiles:
        default_path = get_profile_file_path("default")
        if not os.path.exists(default_path):
            with open(default_path, 'w', encoding='utf-8') as f:
                json.dump({"skills": [], "paths": []}, f)
        profiles.append("default")
        
    return sorted(profiles)

@st.cache_data
def _load_skill_tree(profile):
    skill_tree_file = get_profile_file_path(profile)

    if not os.path.exists(skill_tree_file): return {"skills": [], "paths": []}
    with open(skill_tree_file, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            st.error(f"Error reading or parsing profile: {profile}. It may be corrupted.")
            return {"skills": [], "paths": []}

def load_data(profile):
    return _load_skill_tree(profile).get("skills", [])

def load_defined_paths(profile):
    return _load_skill_tree(profile).get("paths", [])

def save_all_data(data, profile):
    """Saves the entire data object (skills and paths) to the profile file."""
    skill_tree_file = get_profile_file_path(profile)
    with open(skill_tree_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    _load_skill_tree.clear()

def save_data(data, profile):
    current_data = _load_skill_tree(profile)
    current_data["skills"] = data
    save_all_data(current_data, profile)

def save_defined_paths(paths, profile):
    current_data = _load_skill_tree(profile)
    current_data["paths"] = paths
    save_all_data(current_data, profile)

def save_data_and_clear_cache(data, profile):
    save_data(data, profile)
    _calculate_urgency.clear()

def save_defined_paths_and_clear_cache(paths, profile):
    save_defined_paths(paths, profile)
    _load_defined_paths.clear()

@st.cache_data
def _calculate_urgency(skills_tuple):
    skills = [dict(s) for s in skills_tuple]
    for s in skills:
        prio = int(s.get('priority', 1))
        prof = int(s.get('proficiency', 0))
        s['urgency_score'] = prio * (5 - prof)
    return sorted(skills, key=lambda x: x['urgency_score'], reverse=True)

def calculate_urgency(skills):
    return _calculate_urgency(tuple(frozenset(s.items()) for s in skills))

def generate_tree_dot(skills, all_paths, show_leaves=True):
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
            
    if show_leaves:
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

def update_skill_paths(profile, old_path, new_path, recursive=True):
    skills, updated_count = load_data(profile), 0
    for s in skills:
        p = s.get('path', '')
        if p == old_path:
            s['path'], updated_count = new_path, updated_count + 1
        elif recursive and p.startswith(old_path + '.'):
            s['path'] = new_path + p[len(old_path):]
            updated_count += 1
    save_data_and_clear_cache(skills, profile)
    return updated_count

def update_defined_paths(profile, old_path, new_path, recursive=True):
    paths, new_paths, changed = load_defined_paths(profile), [], False
    for p in paths:
        if p == old_path: new_paths.append(new_path); changed = True
        elif recursive and p.startswith(old_path + '.'): new_paths.append(new_path + p[len(old_path):]); changed = True
        else: new_paths.append(p)
    if changed: save_defined_paths_and_clear_cache(list(set(new_paths)), profile)

def update_path_references(profile, old_path, new_path, recursive=True):
    updated_count = update_skill_paths(profile, old_path, new_path, recursive)
    update_defined_paths(profile, old_path, new_path, recursive)
    return updated_count

# --- Main App ---
st.set_page_config(page_title=t("page_title"), layout="wide")
st.markdown(get_font_css(st.session_state.lang), unsafe_allow_html=True)
st.markdown("""
<style>
    /* Hide the dropdown arrow on all popover buttons for a cleaner UI */
    button[data-testid="stPopover"] > svg {
        display: none;
    }
    /* Use flexbox to make header containers stretch to equal height */
    /* This targets the specific horizontal block in the header by looking for a selectbox inside it */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"]) {
        align-items: stretch;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"]) > div {
        display: flex;
        flex-direction: column;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"]) > div > div[data-testid="stVerticalBlock"] {
        flex-grow: 1;
    }
</style>
""", unsafe_allow_html=True)

migrate_old_profiles()


# Clear new profile input if flagged from a previous run
if st.session_state.get("clear_new_profile_input"):
    st.session_state.new_profile_name_input = ""
    del st.session_state.clear_new_profile_input

# --- Profile Initialization ---
profiles = get_profiles()

# Check for a pending profile change from an action like add/delete
if 'next_active_profile' in st.session_state:
    # Use the pending profile and clear the flag
    st.session_state.active_profile = st.session_state.next_active_profile
    del st.session_state.next_active_profile

# Initialize session state for the profile, prioritizing URL param only if session state is not set
if 'active_profile' not in st.session_state:
    query_profile = st.query_params.get("profile")
    if query_profile and query_profile in profiles:
        st.session_state.active_profile = query_profile
    else:
        st.session_state.active_profile = profiles[0]

# Now, session state is the source of truth. The selectbox will update it.
# We just need to ensure the URL is kept in sync with the session state.
if st.query_params.get("profile") != st.session_state.active_profile:
    st.query_params["profile"] = st.session_state.active_profile

active_profile = st.session_state.active_profile
all_data = load_data(active_profile)
defined_paths = load_defined_paths(active_profile)
existing_skill_paths = [d.get('path', '') for d in all_data if d.get('path')]
all_paths = list(dict.fromkeys(existing_skill_paths + defined_paths))


    
# --- New Header Controls ---
if 'page' not in st.session_state:
    st.session_state.page = "home_view"

def set_page(page_name):
    st.session_state.page = page_name

col1, col2 = st.columns([0.6, 0.4])

with col1:
    with st.container(border=True):
        cols = st.columns(2)
        with cols[0]:
            st.button(
                t("home_view"), 
                on_click=set_page, 
                args=("home_view",), 
                use_container_width=True, 
                type="primary" if st.session_state.page == "home_view" else "secondary"
            )
        with cols[1]:
            st.button(
                t("manage_view"), 
                on_click=set_page, 
                args=("manage_view",), 
                use_container_width=True, 
                type="primary" if st.session_state.page == "manage_view" else "secondary"
            )

with col2:
    with st.container(border=True):
        l_col, p_col, add_col, del_col = st.columns([3, 5, 1, 1])

        with l_col:
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
                st.session_state.page = "home_view"
                st.rerun()

        with p_col:
            st.selectbox(
                label=t("profile_selector_label"),
                options=profiles,
                key="active_profile",
                label_visibility="collapsed"
            )

        with add_col:
            with st.popover("➕", use_container_width=False):
                st.subheader(t("add_profile_header", "Create New Profile"))
                new_profile_name = st.text_input(t("new_profile_name_label"), placeholder=t("new_profile_name_placeholder"), key="new_profile_name_input")
                if st.button(f'📝 {t("create_profile_button", "Create Profile")}', use_container_width=True):
                    if new_profile_name:
                        sanitized_name = new_profile_name.strip()
                        is_valid, error_msg = is_valid_profilename(sanitized_name)
                        if is_valid and sanitized_name != "default":
                            new_profile_file = get_profile_file_path(sanitized_name)
                            if not os.path.exists(new_profile_file):
                                with open(new_profile_file, 'w', encoding='utf-8') as f:
                                    json.dump({"skills": [], "paths": []}, f, indent=4, ensure_ascii=False)
                                st.session_state.next_active_profile = sanitized_name
                                st.success(t("profile_creation_success").format(name=sanitized_name))
                                st.session_state.clear_new_profile_input = True
                                st.rerun()
                            else:
                                st.error(t("profile_creation_error_exists").format(name=sanitized_name))
                        else:
                            st.warning(error_msg if not is_valid else t("profile_creation_error_empty_or_default", "Profile name cannot be empty or 'default'."))
                    else:
                        st.warning(t("profile_creation_error_empty"))

                st.markdown("---")
                st.subheader(t("import_export_profile_header", "Import / Export Profile"))

                st.download_button(
                    label=f'📥 {t("export_button", "Export Current Profile")}',
                    data=json.dumps(_load_skill_tree(active_profile), indent=4, ensure_ascii=False),
                    file_name=f"skill_tree_{active_profile}.json",
                    mime="application/json",
                    use_container_width=True
                )

                with st.form(key='import_profile_form', clear_on_submit=True):
                    uploaded_file = st.file_uploader(t("import_button", "Import from file"), type="json")
                    submitted = st.form_submit_button(f'📤 {t("import_submit_button", "Import & Overwrite")}')
                    
                    if submitted and uploaded_file is not None:
                        try:
                            new_data = json.load(uploaded_file)
                            # Basic validation
                            if "skills" in new_data and "paths" in new_data:
                                save_all_data(new_data, active_profile)
                                st.success(t("import_success"))
                                # st.rerun() is implicitly called by form submission
                            else:
                                st.error(t("import_error"))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            st.error(t("import_error"))
        
        with del_col:
            with st.popover("⚙️", use_container_width=False):
                st.subheader(t("rename_profile_header", "Rename Profile"))
                profile_to_rename = st.session_state.active_profile
                
                if profile_to_rename == "default":
                    st.info(t("cannot_rename_default", "The 'default' profile cannot be renamed."))
                else:
                    new_profile_name_rename = st.text_input(t("new_profile_name_label", "New profile name"), value=profile_to_rename, key="new_profile_name_rename_input")
                    if st.button(f'✏️ {t("rename_profile_button", "Rename")}', use_container_width=True):
                        sanitized_new_name = new_profile_name_rename.strip()
                        is_valid, error_msg = is_valid_profilename(sanitized_new_name)

                        if not is_valid:
                            st.error(error_msg)
                        elif sanitized_new_name == profile_to_rename:
                            st.warning(t("profile_name_not_changed", "The new name is the same as the old one."))
                        elif os.path.exists(get_profile_file_path(sanitized_new_name)):
                            st.error(t("profile_creation_error_exists").format(name=sanitized_new_name))
                        else:
                            try:
                                os.rename(get_profile_file_path(profile_to_rename), get_profile_file_path(sanitized_new_name))
                                st.session_state.next_active_profile = sanitized_new_name
                                st.success(t("profile_rename_success", "Profile renamed from '{old}' to '{new}'.").format(old=profile_to_rename, new=sanitized_new_name))
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error renaming profile: {e}")

                st.markdown("---")
                st.subheader(t("delete_profile_header", "Delete Profile"))
                profile_to_delete = st.session_state.active_profile
                st.warning(t("delete_profile_warning", "This will permanently delete profile '{profile}'.").format(profile=profile_to_delete))
                
                if st.button(f'🗑️ {t("delete_confirm_button", "Confirm Deletion")}', use_container_width=True, type="primary"):
                    if profile_to_delete == "default":
                        st.error(t("cannot_delete_default_profile_error", "The 'default' profile cannot be deleted."))
                    else:
                        st.session_state.next_active_profile = "default"
                        profile_path = get_profile_file_path(profile_to_delete)
                        try:
                            os.remove(profile_path)
                            st.success(t("profile_deleted_success", "Profile '{profile}' deleted.").format(profile=profile_to_delete))
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting profile: {e}")

# Get the page value for the main logic
page = st.session_state.page
    
with st.sidebar:
    st.title(t("nav_title"))
    st.markdown("---")

if page == "home_view":
    st.title(t("main_title"))
    st.markdown("---")
    with st.sidebar:
        if st.session_state.get("submit_success", False):
            st.session_state.input_name, st.session_state.input_memo, st.session_state.submit_success = "", "", False
            if 'cascading_path_selection' in st.session_state:
                st.session_state.cascading_path_selection = []
        
        st.header(t("add_skill_header"))
        with st.container(border=True):
            st.markdown(f"##### {t('path_box_title')}")
            
            path_tree = build_path_tree(all_paths)
            if 'cascading_path_selection' not in st.session_state:
                st.session_state.cascading_path_selection = []

            current_parts = st.session_state.cascading_path_selection
            
            current_subtree = path_tree
            new_parts = []
            level = 0
            final_path = ""

            while True:
                options = list(current_subtree.keys())
                if not options:
                    final_path = ".".join(new_parts)
                    break

                default_index = 0
                if level < len(current_parts) and current_parts[level] in options:
                    default_index = options.index(current_parts[level]) + 1

                selection = st.selectbox(
                    label=f"{t('level', default='Level')} {level + 1}",
                    options=[''] + options,
                    index=default_index,
                    key=f"path_select_{level}"
                )

                if selection:
                    new_parts.append(selection)
                    current_subtree = current_subtree.get(selection, {})
                    level += 1
                else:
                    final_path = ".".join(new_parts)
                    break
            
            if new_parts != st.session_state.cascading_path_selection:
                st.session_state.cascading_path_selection = new_parts
                st.rerun()

            selected_path = final_path
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
                current_data = all_data.copy()
                current_data.append({"name": name, "path": selected_path, "proficiency": proficiency, "priority": priority, "memo": memo})
                save_data_and_clear_cache(current_data, active_profile)
                st.success(t("success_skill_added").format(name=name))
                st.session_state.submit_success = True
                st.rerun()
            else: st.error(t("error_skill_name_empty") if not name else t("error_path_empty"))

    raw_skills = load_data(active_profile)
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
        tab2, tab1 = st.tabs([t("tab_tree"), t("tab_list")])
        with tab1:
            df = pd.DataFrame(skills).sort_values(by=['path', 'urgency_score'], ascending=[True, False])
            if 'memo' not in df.columns: df['memo'] = ""
            df['path'] = df['path'].astype(str).str.replace('.', ' ➤ ', regex=False)
            df_display = df[['path', 'name', 'proficiency', 'priority', 'urgency_score', 'memo']].rename(columns={'name': t('col_name'), 'path': t('col_path'), 'proficiency': t('col_proficiency'), 'priority': t('col_priority'), 'urgency_score': t('col_urgency'), 'memo': t('col_memo')})
            df_display = df_display.reset_index(drop=True)

            # Header
            header_cols = st.columns([0.2, 0.2, 0.1, 0.1, 0.1, 0.15, 0.15, 0.05, 0.05])
            header_cols[0].markdown(f"**{t('col_path')}**")
            header_cols[1].markdown(f"**{t('col_name')}**")
            header_cols[2].markdown(f"**{t('col_proficiency')}**")
            header_cols[3].markdown(f"**{t('col_priority')}**")
            header_cols[4].markdown(f"**{t('col_urgency')}**")
            header_cols[5].markdown(f"**{t('col_memo')}**")
            header_cols[6].markdown(f"**{t('edit_mode_toggle')}**")


            for i, row in df_display.iterrows():
                cols = st.columns([0.2, 0.2, 0.1, 0.1, 0.1, 0.15, 0.15, 0.05, 0.05])
                with cols[0]:
                    st.write(row[t('col_path')])
                with cols[1]:
                    st.write(row[t('col_name')])
                with cols[2]:
                    prof_val = row[t('col_proficiency')]
                    st.markdown(color_box(prof_val, get_proficiency_color(prof_val)), unsafe_allow_html=True)
                with cols[3]:
                    prio_val = row[t('col_priority')]
                    st.markdown(color_box(prio_val, get_priority_color(prio_val)), unsafe_allow_html=True)
                with cols[4]:
                    st.write(row[t('col_urgency')])
                with cols[5]:
                    st.write(row[t('col_memo')])
                with cols[6]:
                    with st.popover(t("edit_mode_toggle"), use_container_width=True):
                        st.subheader(t("edit_skill_header"))
                        
                        edited_name = st.text_input(t("skill_name_label"), value=row[t('col_name')], key=f"name_{i}")
                        
                        all_paths_options = all_paths
                        path_str = row[t('col_path')].replace(' ➤ ', '.') if isinstance(row[t('col_path')], str) else ''
                        selected_path_index = all_paths_options.index(path_str) if path_str in all_paths_options else 0
                        edited_path = st.selectbox(t("path_box_title"), options=all_paths_options, index=selected_path_index, key=f"path_{i}")

                        edited_proficiency = st.radio(t("proficiency_label"), options=[5, 4, 3, 2, 1, 0], index=[5, 4, 3, 2, 1, 0].index(row[t('col_proficiency')]), key=f"prof_{i}")
                        edited_priority = st.radio(t("priority_label"), options=[3, 2, 1], index=[3, 2, 1].index(row[t('col_priority')]), key=f"prio_{i}")
                        edited_memo = st.text_area(t("memo_label"), value=row[t('col_memo')], key=f"memo_{i}")

                        if st.button(t("save_skill_button"), key=f"save_{i}"):
                            current_data = all_data.copy()
                            
                            original_skill_index = -1
                            for idx, skill in enumerate(current_data):
                                if skill['name'] == row[t('col_name')] and skill.get('path', '') == path_str:
                                    original_skill_index = idx
                                    break
                            
                            if original_skill_index != -1:
                                current_data[original_skill_index] = {
                                    "name": edited_name,
                                    "path": edited_path,
                                    "proficiency": edited_proficiency,
                                    "priority": edited_priority,
                                    "memo": edited_memo
                                }
                                save_data_and_clear_cache(current_data, active_profile)
                                st.success(t("success_data_updated"))
                                st.rerun()
                            else:
                                st.error("Could not find the skill to update.")
                with cols[7]:
                    if st.button(t("action_move_up"), key=f"up_{i}"):
                        current_data = all_data.copy()
                        original_skill_index = -1
                        path_str = row[t('col_path')].replace(' ➤ ', '.') if isinstance(row[t('col_path')], str) else ''
                        for idx, skill in enumerate(current_data):
                            if skill['name'] == row[t('col_name')] and skill.get('path', '') == path_str:
                                original_skill_index = idx
                                break
                        if original_skill_index > 0:
                            current_data.insert(original_skill_index - 1, current_data.pop(original_skill_index))
                            save_data_and_clear_cache(current_data, active_profile)
                            st.rerun()

                with cols[8]:
                    if st.button(t("action_move_down"), key=f"down_{i}"):
                        current_data = all_data.copy()
                        original_skill_index = -1
                        path_str = row[t('col_path')].replace(' ➤ ', '.') if isinstance(row[t('col_path')], str) else ''
                        for idx, skill in enumerate(current_data):
                            if skill['name'] == row[t('col_name')] and skill.get('path', '') == path_str:
                                original_skill_index = idx
                                break
                        if original_skill_index < len(current_data) - 1:
                            current_data.insert(original_skill_index + 1, current_data.pop(original_skill_index))
                            save_data_and_clear_cache(current_data, active_profile)
                            st.rerun()

            
            # The dataframe is no longer needed as the data is displayed in a custom grid above.
            # I will leave the color functions in case they are needed in the future.
        with tab2:
            show_leaves = st.toggle(t("show_skill_nodes"), value=True, key="toggle_leaves_home")
            st.caption(t("tree_legend"))
            st.graphviz_chart(generate_tree_dot(skills, all_paths, show_leaves=show_leaves))
    else: st.info(t("empty_tree_info"))
elif page == "manage_view":
    st.title(t("manage_page_title"))
    st.info(t("manage_page_info"))
    with st.container(border=True):
        st.subheader(t("graph_header"))
        if all_data or all_paths:
            show_leaves_manage = st.toggle(t("show_skill_nodes"), value=True, key="toggle_leaves_manage")
            st.caption(t("tree_legend"))
            st.graphviz_chart(generate_tree_dot(all_data, all_paths, show_leaves=show_leaves_manage))
        else: st.info(t("empty_graph_info"))
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader(t("add_path_header"))

            st.markdown(f"**{t('select_parent_step1')}**")
    
            parent_path_key = 'add_path_parent_parts'
            if parent_path_key not in st.session_state:
                st.session_state[parent_path_key] = []
                
            path_tree = build_path_tree(all_paths)
            
            parent_type = st.radio(
                "Parent Type", 
                [t("parent_top_level"), t("existing_path")],
                horizontal=True, 
                label_visibility="collapsed"
            )

            selected_parent = t("parent_top_level")

            if parent_type == t("existing_path"):
                current_subtree = path_tree
                new_parent_parts = []
                level = 0
                while True:
                    options = list(current_subtree.keys())
                    if not options: break
                    
                    default_index = 0
                    if level < len(st.session_state[parent_path_key]) and st.session_state[parent_path_key][level] in options:
                        default_index = options.index(st.session_state[parent_path_key][level]) + 1
                    
                    selection = st.selectbox(
                        f"{t('level', default='Level')} {level + 1}", 
                        [''] + options, 
                        index=default_index, 
                        key=f"add_parent_path_L{level}"
                    )
                    
                    if selection:
                        new_parent_parts.append(selection)
                        current_subtree = current_subtree.get(selection, {})
                        level += 1
                    else:
                        break
                
                if st.session_state[parent_path_key] != new_parent_parts:
                    st.session_state[parent_path_key] = new_parent_parts
                    st.rerun()
                    
                selected_parent = ".".join(st.session_state[parent_path_key])
            else:
                if st.session_state[parent_path_key]:
                    st.session_state[parent_path_key] = []
                    st.rerun()
            
            st.caption(t('path_to_be_added_to').format(path=selected_parent) if selected_parent != t("parent_top_level") else t("add_to_top_level"))
            
            new_part = st.text_input(t("add_child_step2"), placeholder=t("add_child_placeholder"))
            if st.button(t("add_node_button"), type="primary", use_container_width=True):
                if new_part:
                    new_part = new_part.strip().replace(".", "_")
                    if not new_part: st.warning(t("error_name_empty"))
                    else:
                        new_path_def = f"{selected_parent}.{new_part}" if selected_parent != t("parent_top_level") else new_part
                        current_paths = load_defined_paths(active_profile)
                        if new_path_def not in current_paths:
                            current_paths.append(new_path_def); save_defined_paths_and_clear_cache(list(set(current_paths)), active_profile)
                            st.success(t("success_path_added").format(path=new_path_def))
                            st.session_state.remembered_parent = selected_parent # Remember for next time
                            st.rerun()
                        else: st.warning(t("warning_path_exists"))
                else: st.warning(t("error_path_input_empty"))
            with st.expander(t("manual_path_expander")):
                manual_path_def = st.text_input(t("manual_path_input"), key="manual_path_def_page")
                if st.button(t("manual_add_button"), key="manual_add"):
                    if manual_path_def:
                        current_paths = load_defined_paths(active_profile)
                        if manual_path_def not in current_paths:
                            current_paths.append(manual_path_def); save_defined_paths_and_clear_cache(list(set(current_paths)), active_profile)
                            st.success(t("success_path_added").format(path=manual_path_def)); st.rerun()
                        else: st.warning(t("warning_path_exists"))
                    else: st.warning(t("error_path_input_empty"))

    with col2:
        with st.container(border=True):
            st.subheader(t("edit_path_header"))
            if not all_paths: st.warning(t("info_path_not_in_presets"))
            else:
                path_to_edit = st.selectbox(t("select_path_to_edit"), all_paths, key="path_to_edit_selectbox")
                action = st.radio(t("action_type_label"), [t("action_rename"), t("action_delete"), t("action_order")], horizontal=True, key="action_radio")
                if action == t("action_rename"):
                    new_path_name = st.text_input(t("rename_to_label"), value=path_to_edit)
                    recursive = st.checkbox(t("rename_recursive_checkbox"), value=True)
                    if st.button(t("rename_confirm_button"), use_container_width=True):
                        if new_path_name and new_path_name != path_to_edit:
                            count = update_path_references(active_profile, path_to_edit, new_path_name, recursive)
                            st.success(t("success_path_updated").format(count=count)); st.rerun()
                        else: st.warning(t("warning_path_not_changed"))
                elif action == t("action_delete"):
                    st.warning(t("delete_warning").format(path=path_to_edit))
                    st.caption(t("delete_caption"))
                    if st.button(t("delete_confirm_button"), use_container_width=True, type="secondary"):
                        current_paths = load_defined_paths(active_profile)
                        if path_to_edit in current_paths:
                            current_paths.remove(path_to_edit); save_defined_paths_and_clear_cache(current_paths, active_profile)
                            st.success(t("success_path_removed").format(path=path_to_edit)); st.rerun()
                        else: st.info(t("info_path_not_in_presets"))
                elif action == t("action_order"):
                    st.write("---")
                    st.subheader(t("action_order"))
                    
                    paths_to_order = all_paths.copy()

                    for i, path in enumerate(paths_to_order):
                        cols = st.columns([0.8, 0.1, 0.1])
                        with cols[0]:
                            st.write(path)
                        with cols[1]:
                            if i > 0:
                                if st.button(t("action_move_up"), key=f"up_{path}"):
                                    paths_to_order.insert(i - 1, paths_to_order.pop(i))
                                    save_defined_paths_and_clear_cache(paths_to_order, active_profile)
                                    st.rerun()
                        with cols[2]:
                            if i < len(paths_to_order) - 1:
                                if st.button(t("action_move_down"), key=f"down_{path}"):
                                    paths_to_order.insert(i + 1, paths_to_order.pop(i))
                                    save_defined_paths_and_clear_cache(paths_to_order, active_profile)
                                    st.rerun()

