import gradio as gr
import os
from pathlib import Path
from info import get_media_info, convert_file
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_EXTENSIONS = ('.mkv', '.avi', '.mp4', '.m4v')

def get_file_list(directory="/media"):
    files_and_dirs = []
    try:
        # Convert to absolute path and resolve any symlinks
        base_path = Path(directory).resolve()
        logger.info(f"Resolved absolute path: {base_path}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Debug permissions
        logger.info(f"File exists: {base_path.exists()}")
        logger.info(f"Is directory: {base_path.is_dir()}")
        logger.info(f"Current user: {os.getuid()}")
        logger.info(f"Directory permissions: {oct(os.stat(base_path).st_mode)[-3:]}")
        
        if not base_path.exists():
            logger.error(f"Directory {directory} does not exist")
            return [f"Error: Directory {directory} does not exist"]
        
        if not os.access(directory, os.R_OK):
            logger.error(f"No read permission for directory {directory}")
            return [f"Error: No read permission for {directory}"]
            
        logger.info(f"Scanning directory: {directory}")
        for item in base_path.rglob("*"):
            if item.is_file() and item.suffix.lower() in VALID_EXTENSIONS:
                files_and_dirs.append(str(item))
                logger.debug(f"Found file: {item}")
            elif item.is_dir():
                files_and_dirs.append(str(item))
                logger.debug(f"Found directory: {item}")
                
        if not files_and_dirs:
            logger.warning(f"No files or directories found in {directory}")
            return [f"No files found in {directory}"]
            
        return sorted(files_and_dirs)
        
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {str(e)}")
        return [f"Error: {str(e)}"]

def update_media_info(selected_path):
    if not selected_path:
        return "Please select a file or directory"
    
    path = Path(selected_path)
    if path.is_file():
        info = get_media_info(str(path))
        return f"File: {path.name}\n{info}"
    
    media_info = []
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in VALID_EXTENSIONS:
            info = get_media_info(str(item))
            media_info.append(f"File: {item.name}\n{info}\n")
    
    return "\n".join(media_info) if media_info else "No media files found in directory"

def convert_media(selected_path, output_directory):
    if not selected_path:
        return "Please select a file or directory"
    
    path = Path(selected_path)
    if path.is_file():
        result = convert_file(str(path), output_directory)
        return f"Conversion result for {path.name}:\n{result}"
    
    results = []
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in VALID_EXTENSIONS:
            result = convert_file(str(item), output_directory)
            results.append(f"Conversion result for {item.name}:\n{result}")
    
    return "\n".join(results) if results else "No files converted"

# Create Gradio interface
with gr.Blocks() as app:
    gr.Markdown("# iTunes Video Renamer")
    
    with gr.Row():
        file_list = gr.Dropdown(
            choices=get_file_list(directory="/media"),
            label="Select File or Directory",
            interactive=True
        )
        refresh_btn = gr.Button("Refresh List")
    with gr.Row():
        output_dir = gr.Textbox(
            label="Output Directory",
            value="/media/iTunes/iTunes Media",
            interactive=True
        )
    info_output = gr.Textbox(label="Media Information", lines=10)
    convert_btn = gr.Button("Convert")
    convert_output = gr.Textbox(label="Conversion Output", lines=5)
    
    # Event handlers
    refresh_btn.click(
        fn=lambda: gr.update(choices=get_file_list(directory="/media")),
        outputs=[file_list]
    )
    
    file_list.change(
        fn=update_media_info,
        inputs=[file_list],
        outputs=[info_output]
    )
    
    convert_btn.click(
        fn=convert_media,
        inputs=[file_list, output_dir],
        outputs=[convert_output]
    )

if __name__ == "__main__":
    # Ensure we have absolute paths
    media_path = Path("/media").resolve()
    current_path = Path(".").resolve()
    app.launch(server_name="0.0.0.0", server_port=7860,allowed_paths=[str(current_path), str(media_path)])