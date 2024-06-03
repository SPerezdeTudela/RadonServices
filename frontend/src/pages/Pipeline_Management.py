from typing import Any, Dict, List

import requests
import streamlit as st

from commons.constants.pipeline_constants import ContainerType
from src.frontend_constants import CONTAINER_MODE, PIPELINE_DESCRIPTIONS
from src.interfaces import get_orchestrator_url

st.set_page_config(page_title=f"Pipeline Status ({CONTAINER_MODE})")


@st.cache_data
def get_pipelines() -> Dict[ContainerType, List[Dict[str, Any]]]:
    pipelines = {}
    for container_type in ContainerType.get_pipeline_types():
        container_type_str = container_type.value
        response = requests.get(f"{get_orchestrator_url()}/pipelines/{container_type_str}")
        if response.status_code != 200:
            continue
        pipelines[container_type] = response.json()["containers"]

    return pipelines


@st.cache_data
def get_pipeline_batch_status(container_id):
    container_status_response = requests.get(f"{get_orchestrator_url()}/pipelines/status/{container_id}")
    if container_status_response.status_code != 200:
        return None
    return container_status_response.json()["status"]


@st.cache_data
def get_pipeline_instant_status(container_id):
    container_status_response = requests.get(f"{get_orchestrator_url()}/pipelines/status/{container_id}?instant=true")
    if container_status_response.status_code != 200:
        return None
    return container_status_response.json()["status"]


def clear_all_cache():
    get_pipelines.clear()
    get_pipeline_batch_status.clear()
    get_pipeline_instant_status.clear()


def parse_int_or_default(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


# State variables
if "create_pipeline_response" not in st.session_state:
    st.session_state.create_pipeline_response_code = None
    st.session_state.create_pipeline_response = None

# Website starts
st.title("Pipeline Management")
with st.sidebar:
    st.button(label="Clear Cache & Refresh", on_click=clear_all_cache)

# Pipeline Creation
st.header("Create New Pipeline")
pipeline_type = st.selectbox("Pipeline Type", PIPELINE_DESCRIPTIONS.keys())
st.write(PIPELINE_DESCRIPTIONS[pipeline_type])

# ======================================================================
# Pipeline Configurations
pipeline_config_expander = st.expander("Pipeline configurations", expanded=False)

# Global configurations (for all pipelines)
pipeline_config: Dict[str, Any] = {
    "fits_volume_path": pipeline_config_expander.text_input("FITS Path", value="/sharedata/raid0hdd/neo/data/fits"),
    # Also has 'image_repository' and 'image_tag', but those can be pre-filled based on pipeline type
}

# Pipeline-specific configurations
if pipeline_type == "fetch":
    cols: List[st.delta_generator.DeltaGenerator] = pipeline_config_expander.columns(2)
    pipeline_config["image_repository"]: str = cols[0].text_input("Image Repository", value="dockerneoc/radon")
    pipeline_config["image_tag"]: str = cols[1].text_input("Image Tag", value="pipeline-fetch")

    pipeline_config["env_sql_batch_size"]: int = cols[0].number_input("Batch Size", value=200, min_value=100, max_value=500)
    pipeline_config["env_max_fails"]: int = cols[1].number_input("Max Fails", value=1, min_value=1, max_value=5)
elif pipeline_type == "radon":
    cols: List[st.delta_generator.DeltaGenerator] = pipeline_config_expander.columns(2)
    pipeline_config["image_repository"]: str = cols[0].text_input("Image Repository", value="dockerneoc/radon")
    pipeline_config["image_tag"]: str = cols[1].text_input("Image Tag", value="pipeline-radon")
elif pipeline_type == "augment":
    cols: List[st.delta_generator.DeltaGenerator] = pipeline_config_expander.columns(2)
    pipeline_config["image_repository"]: str = cols[0].text_input("Image Repository", value="dockerneoc/radon")
    pipeline_config["image_tag"]: str = cols[1].text_input("Image Tag", value="pipeline-augment")

pipeline_config_expander.write("**Final Configurations:**")
pipeline_config_expander.write(pipeline_config)

# ======================================================================
create_pipeline_button = st.button(label="Create Pipeline")
if create_pipeline_button:
    response = requests.post(f"{get_orchestrator_url()}/pipelines/{pipeline_type}", json=pipeline_config)
    st.session_state.create_pipeline_response_code = response.status_code
    st.session_state.create_pipeline_response = response.json()
    clear_all_cache()

if st.session_state.create_pipeline_response_code is None:
    pass
elif st.session_state.create_pipeline_response_code != 200:
    st.write(f"Failed to create pipeline: [{st.session_state.create_pipeline_response_code}] {st.session_state.create_pipeline_response['message']}")
else:
    st.write(f"Created new '{st.session_state.create_pipeline_response['new_pipeline']}' pipeline at port {st.session_state.create_pipeline_response['ports']}")

# ======================================================================
# Pipeline status
st.divider()
st.header("Pipeline Status")
pipelines: Dict[ContainerType, List[Dict[str, Any]]] = get_pipelines()

if not pipelines:
    st.write("No active pipelines")
    st.stop()

pipeline_types: List[ContainerType] = ContainerType.get_pipeline_types()
tabs = st.tabs([f"{p_type.value.title()} ({len(pipelines.get(p_type, []))})" for p_type in pipeline_types])
for tab_index, pipeline_type in enumerate(pipeline_types):
    tab_index: int
    pipeline_type: ContainerType

    containers: List[Dict[str, Any]] = pipelines.get(pipeline_type, [])
    with tabs[tab_index]:
        for i, container in enumerate(containers):
            with st.container(border=True):
                st.write(f"**Container:** {container['name']} #({container['id']})")
                st.write(f"**Host:** {container['hostname']}:{container['port']}")
                st.write(f"**Status:** {container['status']}")

                # Get container status
                status_json = get_pipeline_instant_status(container['id'])
                if status_json is None:
                    st.write(f"Failed to get container status")
                else:
                    iteration = status_json.get("iteration", "Unknown")
                    progress = status_json.get("iteration_progress", 0)
                    max_progress = status_json.get("iteration_max_progress", 100)
                    progress_percent = progress / max_progress
                    st.progress(progress_percent, text=f"Iteration {iteration} -- ({progress}/{max_progress})")

                # Shutdown button
                shutdown_button = st.button(label="Shutdown Container", key=container['id'])
                if shutdown_button:
                    response = requests.delete(f"{get_orchestrator_url()}/pipelines/{pipeline_type.value}", json={"container_id": container['id']})
                    if response.status_code != 200:
                        st.write(f"Failed to shutdown container: {response.json()['error']}")
                    else:
                        st.write(f"Successfully sent shutdown command to container")
                    clear_all_cache()
