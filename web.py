import gradio as gr
import os
from pathlib import Path
from info import get_media_info, convert_file
import logging
import glob
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=7860, help='Port number to run server on')
parser.add_argument('--log', type=bool, default=False, help='enable logging')
args = parser.parse_args()

if args.log:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
else:
    logger = logging.getLogger(__name__)
    logger.disabled = True


VALID_EXTENSIONS = ('.mkv', '.avi', '.mp4', '.m4v')

def update_media_info(selected_path):
    if not selected_path:
        return "Please select a file or directory"
    
    if not isinstance(selected_path,list):
        selected_path = [selected_path]

    output = ""

    #build up a string of media info
    for path in selected_path:
        path = Path(path)
        if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS:
            info = get_media_info(str(path))
            output += f"File: {path.name}\n{info}\n\n"
    
    return output

def convert_media(selected_path, output_directory,output_log):
    if not selected_path:
        return "Please select a file or directory"
    
    ret = output_log

    if not isinstance(selected_path,list):
        selected_path = [selected_path]
    
    for path in selected_path:
        for message in convert_file(str(path), output_directory):
            output_log += message
            yield output_log
            logger.warning("FROM YIELD!!" + message)

    return ret
    # Set up argument parser


# Create Gradio interface
with gr.Blocks() as app:
    gr.Markdown("# iTunes Video Renamer")
    output_log = gr.State("")
    with gr.Row():
        file_types = gr.Dropdown(
            label="Select a File Type",
            choices=["[ammm][vk4p4][iv4v]","mkv","mp4","avi","m4v"],
            interactive=True
        )
    with gr.Row():
        selected_path = gr.FileExplorer(
            root_dir="/media/torrent",
            glob="**/*." + file_types.value,
            label="Select File or Directory"
        )
    
    def update_glob(file_type):
        return gr.FileExplorer(root_dir="/media/torrent", glob=f"**/*.{file_type}",label="Select File or Directory")
    
    file_types.change(
        fn=update_glob,
        inputs=file_types,
        outputs=selected_path
    )
    with gr.Row():
        output_dir = gr.Textbox(
            label="Output Directory",
            value="/media/torrent/Output",
            interactive=True
        )
    info_output = gr.Textbox(label="Media Information", lines=10)
    convert_btn = gr.Button("Convert")
    convert_output = gr.Textbox(label="Conversion Output", lines=5)
    
    selected_path.change(
        fn=update_media_info,
        inputs=selected_path,
        outputs=info_output
    )
    convert_btn.click(
        fn=convert_media,
        inputs=[selected_path, output_dir,output_log],
        outputs=[convert_output]
    )
if __name__ == "__main__":
    # Ensure we have absolute paths
    media_path = Path("/media").resolve()
    current_path = Path(".").resolve()
    app.queue().launch(server_name="0.0.0.0", server_port=args.port, allowed_paths=[str(current_path), str(media_path)])