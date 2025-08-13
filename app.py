from dotenv import load_dotenv
import json
import logging
import logging.config
import os
import re
from services import bedrock_agent_runtime
import streamlit as st
import uuid
import yaml
from datetime import datetime

load_dotenv()
st.set_page_config(
    page_title="Your App",
    layout="wide"
)

# Add this at the top of your main script
if 'first_run' not in st.session_state:
    st.session_state.first_run = True
    st.rerun()
    
# Configure logging using YAML
if os.path.exists("logging.yaml"):
    with open("logging.yaml", "r") as file:
        config = yaml.safe_load(file)
        logging.config.dictConfig(config)
else:
    log_level = logging.getLevelNamesMapping()[(os.environ.get("LOG_LEVEL", "INFO"))]
    logging.basicConfig(level=log_level)

logger = logging.getLogger(__name__)

# Get config from environment variables
agent_id = os.environ.get("BEDROCK_AGENT_ID")
agent_alias_id = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID") # TSTALIASID is the default test alias ID
ui_title = os.environ.get("BEDROCK_AGENT_TEST_UI_TITLE", "Agents for Amazon Bedrock Test UI")
ui_icon = os.environ.get("BEDROCK_AGENT_TEST_UI_ICON")

def init_session_state():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.citation_nums = []
    st.session_state.citations = []
    st.session_state.titan_citation_style = False
    st.session_state.trace = {}
    st.session_state.email_sent = {} # To track messages sent by email
    st.session_state.show_trace = False # To hide/show the Trace block

# General page configuration and initialization
st.set_page_config(page_title=ui_title, page_icon=ui_icon, layout="wide")

# Display logo and title side by side
col_logo, col_title = st.columns([1, 4])
with col_logo:
    # Display the Industrial Hive logo
    logo_path = "static/images/logo_ruche_industrielle.png"
    if os.path.exists(logo_path):
        try:
            st.image(logo_path, width=180)
        except Exception as e:
            st.error(f"Error loading logo: {e}")
            logger.error(f"Error loading logo: {e}")

with col_title:
    st.title(ui_title)

if len(st.session_state.items()) == 0:
    init_session_state()

# Sidebar button to reset session state
with st.sidebar:
    usr_container_width = True
    
    if st.button("Reset session", use_container_width=usr_container_width):
        init_session_state()
    
    # Quick access buttons for specific prompts
    col1 = st.container()
    col2 = st.container()
    col3 = st.container()
    col4 = st.container()
    
    with col1:
        if st.button("🏭 Workshop Status", use_container_width=usr_container_width):
            prompt = "Give me a production status summary for all machines in the workshop on 06/20/2023?"
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.spinner():
                response = bedrock_agent_runtime.invoke_agent(
                    agent_id,
                    agent_alias_id,
                    st.session_state.session_id,
                    prompt
                )
            output_text = response["output_text"]

            # Process response (same as in chat input)
            st.session_state.titan_citation_style = False
            try:
                output_json = json.loads(output_text, strict=False)
                if "instruction" in output_json and "result" in output_json:
                    output_text = output_json["result"]
                    st.session_state.titan_citation_style = "%[X]%" in output_json["instruction"]
            except json.JSONDecodeError as e:
                pass

            # Add citations
            if len(response["citations"]) > 0:
                citation_nums = []

                def replace_citation(match):
                    global citation_nums
                    orig_citation_num = match.group(1)
                    citation_nums.append(orig_citation_num)
                    return f"<sup>[{orig_citation_num}]</sup>"

                if st.session_state.titan_citation_style:
                    output_text = re.sub(r"%\[(\d+)\]%", replace_citation, output_text)

                i = 0
                citation_locs = {}
                for citation in response["citations"]:
                    for retrieved_ref in citation["retrievedReferences"]:
                        citation_num = i + 1
                        if st.session_state.titan_citation_style:
                            citation_num = citation_nums[i]
                        if citation_num not in citation_locs.keys():
                            citation_marker = f"[{citation_num}]"
                            match retrieved_ref['location']['type']:
                                case 'CONFLUENCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['confluenceLocation']['url']}"
                                case 'CUSTOM':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['customDocumentLocation']['id']}"
                                case 'KENDRA':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['kendraDocumentLocation']['uri']}"
                                case 'S3':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['s3Location']['uri']}"
                                case 'SALESFORCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['salesforceLocation']['url']}"
                                case 'SHAREPOINT':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sharePointLocation']['url']}"
                                case 'SQL':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sqlLocation']['query']}"
                                case 'WEB':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['webLocation']['url']}"
                                case _:
                                    logger.warning(f"Unknown location type: {retrieved_ref['location']['type']}")
                        i += 1
                citation_locs = dict(sorted(citation_locs.items(), key=lambda item: int(item[0])))
                st.session_state.citation_nums = citation_nums

                output_text += "\n"
                for citation_num, citation_loc in citation_locs.items():
                    output_text += f"\n<br>[{citation_num}] {citation_loc}"

            st.session_state.messages.append({"role": "assistant", "content": output_text})
            st.session_state.citations = response["citations"]
            st.session_state.trace = response["trace"]

    with col2:
        if st.button("⚙️ Press 48065 Status", use_container_width=usr_container_width):
            prompt = "Give me a summary of work orders, stoppages, rejects, major configuration changes, and leak tests for press 48065 on 06/20/2023?"
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.spinner():
                response = bedrock_agent_runtime.invoke_agent(
                    agent_id,
                    agent_alias_id,
                    st.session_state.session_id,
                    prompt
                )
            output_text = response["output_text"]

            # Process response (same as in chat input)
            st.session_state.titan_citation_style = False
            try:
                output_json = json.loads(output_text, strict=False)
                if "instruction" in output_json and "result" in output_json:
                    output_text = output_json["result"]
                    st.session_state.titan_citation_style = "%[X]%" in output_json["instruction"]
            except json.JSONDecodeError as e:
                pass

            # Add citations
            if len(response["citations"]) > 0:
                citation_nums = []

                def replace_citation(match):
                    global citation_nums
                    orig_citation_num = match.group(1)
                    citation_nums.append(orig_citation_num)
                    return f"<sup>[{orig_citation_num}]</sup>"

                if st.session_state.titan_citation_style:
                    output_text = re.sub(r"%\[(\d+)\]%", replace_citation, output_text)

                i = 0
                citation_locs = {}
                for citation in response["citations"]:
                    for retrieved_ref in citation["retrievedReferences"]:
                        citation_num = i + 1
                        if st.session_state.titan_citation_style:
                            citation_num = citation_nums[i]
                        if citation_num not in citation_locs.keys():
                            citation_marker = f"[{citation_num}]"
                            match retrieved_ref['location']['type']:
                                case 'CONFLUENCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['confluenceLocation']['url']}"
                                case 'CUSTOM':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['customDocumentLocation']['id']}"
                                case 'KENDRA':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['kendraDocumentLocation']['uri']}"
                                case 'S3':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['s3Location']['uri']}"
                                case 'SALESFORCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['salesforceLocation']['url']}"
                                case 'SHAREPOINT':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sharePointLocation']['url']}"
                                case 'SQL':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sqlLocation']['query']}"
                                case 'WEB':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['webLocation']['url']}"
                                case _:
                                    logger.warning(f"Unknown location type: {retrieved_ref['location']['type']}")
                        i += 1
                citation_locs = dict(sorted(citation_locs.items(), key=lambda item: int(item[0])))
                st.session_state.citation_nums = citation_nums

                output_text += "\n"
                for citation_num, citation_loc in citation_locs.items():
                    output_text += f"\n<br>[{citation_num}] {citation_loc}"

            st.session_state.messages.append({"role": "assistant", "content": output_text})
            st.session_state.citations = response["citations"]
            st.session_state.trace = response["trace"]

    with col3:
        if st.button("☔️ Leak Diagnosis", use_container_width=usr_container_width):
            prompt = "I have a leak problem with the parts. Help me diagnose it."
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.spinner():
                response = bedrock_agent_runtime.invoke_agent(
                    agent_id,
                    agent_alias_id,
                    st.session_state.session_id,
                    prompt
                )
            output_text = response["output_text"]

            # Process response (same as in chat input)
            st.session_state.titan_citation_style = False
            try:
                output_json = json.loads(output_text, strict=False)
                if "instruction" in output_json and "result" in output_json:
                    output_text = output_json["result"]
                    st.session_state.titan_citation_style = "%[X]%" in output_json["instruction"]
            except json.JSONDecodeError as e:
                pass

            # Add citations
            if len(response["citations"]) > 0:
                citation_nums = []

                def replace_citation(match):
                    global citation_nums
                    orig_citation_num = match.group(1)
                    citation_nums.append(orig_citation_num)
                    return f"<sup>[{orig_citation_num}]</sup>"

                if st.session_state.titan_citation_style:
                    output_text = re.sub(r"%\[(\d+)\]%", replace_citation, output_text)

                i = 0
                citation_locs = {}
                for citation in response["citations"]:
                    for retrieved_ref in citation["retrievedReferences"]:
                        citation_num = i + 1
                        if st.session_state.titan_citation_style:
                            citation_num = citation_nums[i]
                        if citation_num not in citation_locs.keys():
                            citation_marker = f"[{citation_num}]"
                            match retrieved_ref['location']['type']:
                                case 'CONFLUENCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['confluenceLocation']['url']}"
                                case 'CUSTOM':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['customDocumentLocation']['id']}"
                                case 'KENDRA':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['kendraDocumentLocation']['uri']}"
                                case 'S3':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['s3Location']['uri']}"
                                case 'SALESFORCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['salesforceLocation']['url']}"
                                case 'SHAREPOINT':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sharePointLocation']['url']}"
                                case 'SQL':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sqlLocation']['query']}"
                                case 'WEB':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['webLocation']['url']}"
                                case _:
                                    logger.warning(f"Unknown location type: {retrieved_ref['location']['type']}")
                        i += 1
                citation_locs = dict(sorted(citation_locs.items(), key=lambda item: int(item[0])))
                st.session_state.citation_nums = citation_nums

                output_text += "\n"
                for citation_num, citation_loc in citation_locs.items():
                    output_text += f"\n<br>[{citation_num}] {citation_loc}"

            st.session_state.messages.append({"role": "assistant", "content": output_text})
            st.session_state.citations = response["citations"]
            st.session_state.trace = response["trace"]
            
    with col4:
        if st.button("✉️ Send by Email", use_container_width=usr_container_width):
            prompt = "what's happening with press 48068?"
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.spinner():
                response = bedrock_agent_runtime.invoke_agent(
                    agent_id,
                    agent_alias_id,
                    st.session_state.session_id,
                    prompt
                )
            output_text = response["output_text"]

            # Process response (same as in chat input)
            st.session_state.titan_citation_style = False
            try:
                output_json = json.loads(output_text, strict=False)
                if "instruction" in output_json and "result" in output_json:
                    output_text = output_json["result"]
                    st.session_state.titan_citation_style = "%[X]%" in output_json["instruction"]
            except json.JSONDecodeError as e:
                pass

            # Add citations
            if len(response["citations"]) > 0:
                citation_nums = []

                def replace_citation(match):
                    global citation_nums
                    orig_citation_num = match.group(1)
                    citation_nums.append(orig_citation_num)
                    return f"<sup>[{orig_citation_num}]</sup>"

                if st.session_state.titan_citation_style:
                    output_text = re.sub(r"%\[(\d+)\]%", replace_citation, output_text)

                i = 0
                citation_locs = {}
                for citation in response["citations"]:
                    for retrieved_ref in citation["retrievedReferences"]:
                        citation_num = i + 1
                        if st.session_state.titan_citation_style:
                            citation_num = citation_nums[i]
                        if citation_num not in citation_locs.keys():
                            citation_marker = f"[{citation_num}]"
                            match retrieved_ref['location']['type']:
                                case 'CONFLUENCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['confluenceLocation']['url']}"
                                case 'CUSTOM':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['customDocumentLocation']['id']}"
                                case 'KENDRA':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['kendraDocumentLocation']['uri']}"
                                case 'S3':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['s3Location']['uri']}"
                                case 'SALESFORCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['salesforceLocation']['url']}"
                                case 'SHAREPOINT':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sharePointLocation']['url']}"
                                case 'SQL':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sqlLocation']['query']}"
                                case 'WEB':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['webLocation']['url']}"
                                case _:
                                    logger.warning(f"Unknown location type: {retrieved_ref['location']['type']}")
                        i += 1
                citation_locs = dict(sorted(citation_locs.items(), key=lambda item: int(item[0])))
                st.session_state.citation_nums = citation_nums

                output_text += "\n"
                for citation_num, citation_loc in citation_locs.items():
                    output_text += f"\n<br>[{citation_num}] {citation_loc}"

            st.session_state.messages.append({"role": "assistant", "content": output_text})
            st.session_state.citations = response["citations"]
            st.session_state.trace = response["trace"]

# Display conversation messages after the buttons
st.markdown("---")
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)

# Chat input that invokes the agent
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.empty():
            with st.spinner():
                response = bedrock_agent_runtime.invoke_agent(
                    agent_id,
                    agent_alias_id,
                    st.session_state.session_id,
                    prompt
                )
            output_text = response["output_text"]

            # An agent that uses Titan as the FM and has knowledge bases attached may return a JSON object with the
            # instruction and result fields
            st.session_state.titan_citation_style = False
            try:
                # When parsing the JSON, strict mode must be disabled to handle badly escaped newlines
                output_json = json.loads(output_text, strict=False)
                if "instruction" in output_json and "result" in output_json:
                    output_text = output_json["result"]
                    st.session_state.titan_citation_style = "%[X]%" in output_json["instruction"]
            except json.JSONDecodeError as e:
                pass

            # Add citations
            if len(response["citations"]) > 0:
                citation_nums = []

                # Citations in response from agents that use Titan as the FM may be out sequence
                # Thus we need to renumber them
                def replace_citation(match):
                    global citation_nums
                    orig_citation_num = match.group(1)
                    citation_nums.append(orig_citation_num)
                    return f"<sup>[{orig_citation_num}]</sup>"

                if st.session_state.titan_citation_style:
                    output_text = re.sub(r"%\[(\d+)\]%", replace_citation, output_text)

                i = 0
                citation_locs = {}
                for citation in response["citations"]:
                    for retrieved_ref in citation["retrievedReferences"]:
                        citation_num = i + 1
                        if st.session_state.titan_citation_style:
                            citation_num = citation_nums[i]
                        if citation_num not in citation_locs.keys():
                            citation_marker = f"[{citation_num}]"
                            match retrieved_ref['location']['type']:
                                case 'CONFLUENCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['confluenceLocation']['url']}"
                                case 'CUSTOM':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['customDocumentLocation']['id']}"
                                case 'KENDRA':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['kendraDocumentLocation']['uri']}"
                                case 'S3':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['s3Location']['uri']}"
                                case 'SALESFORCE':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['salesforceLocation']['url']}"
                                case 'SHAREPOINT':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sharePointLocation']['url']}"
                                case 'SQL':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['sqlLocation']['query']}"
                                case 'WEB':
                                    citation_locs[citation_num] = f"{retrieved_ref['location']['webLocation']['url']}"
                                case _:
                                    logger.warning(f"Unknown location type: {retrieved_ref['location']['type']}")
                        i += 1
                citation_locs = dict(sorted(citation_locs.items(), key=lambda item: int(item[0])))
                st.session_state.citation_nums = citation_nums

                output_text += "\n"
                for citation_num, citation_loc in citation_locs.items():
                    output_text += f"\n<br>[{citation_num}] {citation_loc}"

            st.session_state.messages.append({"role": "assistant", "content": output_text})
            st.session_state.citations = response["citations"]
            st.session_state.trace = response["trace"]
            st.markdown(output_text, unsafe_allow_html=True)

trace_types_map = {
    "Pre-Processing": ["preGuardrailTrace", "preProcessingTrace"],
    "Orchestration": ["orchestrationTrace"],
    "Post-Processing": ["postProcessingTrace", "postGuardrailTrace"]
}

trace_info_types_map = {
    "preProcessingTrace": ["modelInvocationInput", "modelInvocationOutput"],
    "orchestrationTrace": ["invocationInput", "modelInvocationInput", "modelInvocationOutput", "observation", "rationale"],
    "postProcessingTrace": ["modelInvocationInput", "modelInvocationOutput", "observation"]
}

# Sidebar section for trace
with st.sidebar:
    # Option to show/hide the Trace block
    show_trace = st.checkbox("Show traces", value=st.session_state.get("show_trace", False))
    st.session_state.show_trace = show_trace
    
    if st.session_state.show_trace:
        st.title("Trace")

        # Show each trace type in separate sections
        step_num = 1
        for trace_type_header in trace_types_map:
            st.subheader(trace_type_header)

            # Organize traces by step similar to how it is shown in the Bedrock console
            has_trace = False
            for trace_type in trace_types_map[trace_type_header]:
                if trace_type in st.session_state.trace:
                    has_trace = True
                    trace_steps = {}
                    
                    for trace in st.session_state.trace[trace_type]:
                        # Each trace type and step may have different information for the end-to-end flow
                        if trace_type in trace_info_types_map:
                            trace_info_types = trace_info_types_map[trace_type]
                            for trace_info_type in trace_info_types:
                                if trace_info_type in trace:
                                    trace_id = trace[trace_info_type]["traceId"]
                                    if trace_id not in trace_steps:
                                        trace_steps[trace_id] = [trace]
                                    else:
                                        trace_steps[trace_id].append(trace)
                                    break
                        else:
                            trace_id = trace["traceId"]
                            trace_steps[trace_id] = [
                                {
                                    trace_type: trace
                                }
                            ]

                    # Show trace steps in JSON similar to the Bedrock console
                    for trace_id in trace_steps.keys():
                        with st.expander(f"Trace Step {str(step_num)}", expanded=False):
                            for trace in trace_steps[trace_id]:
                                # Utiliser un JSON encoder personnalisé pour gérer les objets datetime
                                trace_str = json.dumps(trace, indent=2, default=lambda obj: obj.isoformat() if isinstance(obj, datetime) else str(obj))
                                st.code(trace_str, language="json", line_numbers=True, wrap_lines=True)
                        step_num += 1
        if not has_trace:
            st.text("None")

        st.subheader("Citations")
        if len(st.session_state.citations) > 0:
            unique_citation_counts = {}
            i = 0
            for citation in st.session_state.citations:
                for retrieved_ref in citation["retrievedReferences"]:
                    citation_num = f"{i + 1}"
                    if st.session_state.titan_citation_style:
                        citation_num = st.session_state.citation_nums[i]
                    if citation_num not in unique_citation_counts.keys():
                        unique_citation_counts[citation_num] = 1
                    else:
                        unique_citation_counts[citation_num] += 1
                    with st.expander(f"Citation [{citation_num}] - Reference {unique_citation_counts[citation_num]}", expanded=False):
                        citation_str = json.dumps(
                            {
                                "generatedResponsePart": citation["generatedResponsePart"],
                                "retrievedReference": retrieved_ref
                            },
                            indent=2,
                            default=lambda obj: obj.isoformat() if isinstance(obj, datetime) else str(obj)
                        )
                        st.code(citation_str, language="json", line_numbers=True, wrap_lines=True)
                    i += 1
        else:
            st.text("None")
