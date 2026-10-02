"""쇼핑 리스트 Streamlit 앱 (PRD.md 기준, 웹 버전 index.html / script.js를 옮긴 것)

실행: streamlit run app.py
데이터는 브라우저 localStorage 대신 같은 폴더의 shopping_list.json 파일에 저장한다.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).with_name("shopping_list.json")
MAX_NAME_LENGTH = 50


# ===== 유틸 =====


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_name(name) -> str:
    """앞뒤 공백을 없애고 최대 50자로 자른다. 빈 값이면 빈 문자열을 반환한다."""
    return str(name).strip()[:MAX_NAME_LENGTH].strip()


def escape_markdown(text: str) -> str:
    """사용자가 입력한 이름이 마크다운 서식(굵게, 취소선, 링크 등)으로 해석되지 않게 한다."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|~<>$])", r"\\\1", text)


# ===== 저장소 =====


def load_items() -> list[dict]:
    """파일에서 아이템 목록을 불러온다. 손상된 데이터는 걸러내고, 읽을 수 없으면 빈 목록을 반환한다."""
    try:
        parsed = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        st.toast("저장된 쇼핑 리스트를 불러오지 못해 빈 리스트로 시작합니다.", icon="⚠️")
        return []
    if not isinstance(parsed, list):
        return []

    items, seen_ids = [], set()
    for item in parsed:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str):
            continue
        name = normalize_name(item["name"])
        if not name:
            continue
        # 같은 id가 여러 번 나오면 두 번째부터는 새 id를 발급한다.
        item_id = item["id"] if item["id"] and item["id"] not in seen_ids else str(uuid.uuid4())
        seen_ids.add(item_id)
        items.append({
            "id": item_id,
            "name": name,
            "checked": item.get("checked") is True,
            "createdAt": item["createdAt"] if isinstance(item.get("createdAt"), str) else now_iso(),
        })
    return items


def save_items(items: list[dict]) -> None:
    """임시 파일에 쓴 뒤 바꿔치기해서, 저장 중에 멈춰도 파일이 깨지지 않게 한다."""
    try:
        tmp = DATA_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA_FILE)
    except OSError:
        st.toast("쇼핑 리스트를 저장하지 못했습니다.", icon="⚠️")


def mutate(change) -> None:
    """파일에서 최신 목록을 읽어 바꾸고 바로 저장한다.
    매번 파일을 기준으로 하므로, 브라우저 탭을 여러 개 열어도 다른 탭의 변경을 덮어쓰지 않는다."""
    items = load_items()
    change(items)
    save_items(items)


def find(items: list[dict], item_id: str):
    return next((item for item in items if item["id"] == item_id), None)


# ===== 아이템 조작 (위젯 콜백) =====


def add_item() -> None:
    name = normalize_name(st.session_state.new_item)
    st.session_state.new_item = ""
    if not name:
        return
    mutate(lambda items: items.append({"id": str(uuid.uuid4()), "name": name, "checked": False, "createdAt": now_iso()}))


def toggle_item(item_id: str) -> None:
    def change(items):
        item = find(items, item_id)
        if item:
            item["checked"] = st.session_state[f"check_{item_id}"]

    mutate(change)


def delete_item(item_id: str) -> None:
    def change(items):
        items[:] = [item for item in items if item["id"] != item_id]

    mutate(change)
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None


def start_editing(item_id: str, name: str) -> None:
    """편집을 시작한다. 한 번에 하나만 편집하므로 다른 아이템을 편집 중이었다면 그 편집은 취소된다."""
    st.session_state.editing_id = item_id
    st.session_state[f"edit_{item_id}"] = name


def save_edit(item_id: str) -> None:
    """빈 값이면 원래 값을 유지한다."""
    name = normalize_name(st.session_state.get(f"edit_{item_id}", ""))

    def change(items):
        item = find(items, item_id)
        if item and name:
            item["name"] = name

    if name:
        mutate(change)
    st.session_state.editing_id = None


def cancel_edit() -> None:
    st.session_state.editing_id = None


@st.dialog("완료 항목 삭제")
def confirm_clear_completed(count: int) -> None:
    st.write(f"완료한 항목 {count}개를 모두 삭제할까요?")
    left, right = st.columns(2)
    if left.button("삭제", type="primary", use_container_width=True):

        def change(items):
            items[:] = [item for item in items if not item["checked"]]

        mutate(change)
        st.rerun()
    if right.button("취소", use_container_width=True):
        st.rerun()


# ===== 화면 =====

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
st.session_state.setdefault("editing_id", None)

st.markdown(
    """
    <style>
      .block-container { max-width: 560px; padding-top: 2.5rem; }
      /* 체크한 항목: 취소선 + 흐린 색 */
      .st-key-items del { color: var(--checked-color, #6b7280); text-decoration-thickness: 2px; }
      /* 버튼·체크박스 터치 영역 44px 이상 */
      .st-key-items button, .st-key-add_area button { min-height: 44px; min-width: 44px; }
      .st-key-items [data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }
      /* Streamlit은 좁은 화면(640px 미만)에서 열을 세로로 쌓는다.
         아이템 줄과 입력 줄은 360px에서도 한 줄로 유지: 첫 열(이름·입력창)이 남는 폭을 쓰고 버튼 열은 내용만큼만 차지 */
      .st-key-items [data-testid="stHorizontalBlock"],
      .st-key-add_area [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.5rem; }
      .st-key-items [data-testid="stColumn"],
      .st-key-add_area [data-testid="stColumn"] { min-width: 0 !important; }
      .st-key-items [data-testid="stColumn"]:first-child,
      .st-key-add_area [data-testid="stColumn"]:first-child { flex: 1 1 auto !important; width: auto !important; }
      .st-key-items [data-testid="stColumn"]:not(:first-child),
      .st-key-add_area [data-testid="stColumn"]:not(:first-child) { flex: 0 0 auto !important; width: auto !important; }
      .st-key-items [data-testid="stCheckbox"] p { overflow-wrap: anywhere; word-break: keep-all; }
      /* 좁은 화면에서 placeholder와 겹치는 "Press Enter to submit form" 안내 숨김 */
      .st-key-add_area [data-testid="InputInstructions"],
      .st-key-items [data-testid="InputInstructions"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

items = load_items()
# 편집하던 아이템이 다른 탭에서 삭제됐으면 편집을 끝낸다.
if st.session_state.editing_id and not find(items, st.session_state.editing_id):
    st.session_state.editing_id = None

st.title("🛒 쇼핑 리스트")

# --- 아이템 추가: Enter 또는 [추가] ---
# 폼에는 key 클래스가 붙지 않아서, CSS를 적용하려고 key가 있는 컨테이너로 감싼다.
with st.container(key="add_area"), st.form("add_form", border=False):
    col_input, col_button = st.columns([5, 1], vertical_alignment="bottom")
    col_input.text_input(
        "살 물건",
        key="new_item",
        max_chars=MAX_NAME_LENGTH,
        placeholder="살 물건을 입력하세요...",
        label_visibility="collapsed",
    )
    col_button.form_submit_button("추가", type="primary", on_click=add_item, use_container_width=True)

# --- 상태 표시 ---
total = len(items)
completed = sum(item["checked"] for item in items)
st.caption(f"전체 {total}개 · 완료 {completed}개 · 남은 항목 {total - completed}개")

# --- 리스트 ---
with st.container(key="items"):
    if not items:
        st.info("쇼핑 리스트가 비어 있어요. 살 물건을 추가해 보세요!", icon="🧺")

    for item in items:
        item_id, name = item["id"], item["name"]

        if item_id == st.session_state.editing_id:
            # 편집 모드: Enter 또는 [저장] → 저장, [취소] → 취소
            with st.form(f"edit_form_{item_id}", border=True):
                col_edit, col_save, col_cancel = st.columns([4, 1, 1], vertical_alignment="bottom")
                col_edit.text_input(
                    f"{name} 이름 수정",
                    key=f"edit_{item_id}",
                    max_chars=MAX_NAME_LENGTH,
                    label_visibility="collapsed",
                )
                col_save.form_submit_button("저장", type="primary", on_click=save_edit, args=(item_id,), use_container_width=True)
                col_cancel.form_submit_button("취소", on_click=cancel_edit, use_container_width=True)
            continue

        # 다른 탭에서 바뀐 체크 상태도 화면에 반영되도록, 위젯을 만들기 전에 파일 값을 넣는다.
        st.session_state[f"check_{item_id}"] = item["checked"]
        label = f"~~{escape_markdown(name)}~~" if item["checked"] else escape_markdown(name)

        col_check, col_edit, col_delete = st.columns([6, 1, 1], vertical_alignment="center")
        col_check.checkbox(label, key=f"check_{item_id}", on_change=toggle_item, args=(item_id,))
        col_edit.button("수정", key=f"edit_btn_{item_id}", type="tertiary", on_click=start_editing, args=(item_id, name))
        col_delete.button(":red[삭제]", key=f"delete_btn_{item_id}", type="tertiary", on_click=delete_item, args=(item_id,))

# --- 완료 항목 모두 삭제 ---
_, col_clear = st.columns([2, 1])
if col_clear.button("완료 항목 모두 삭제", disabled=completed == 0, use_container_width=True):
    confirm_clear_completed(completed)
