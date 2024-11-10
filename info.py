#! /usr/bin/env -S python3

import os
import re
import sys
import shutil
import subprocess
import requests
from pathlib import Path
import tempfile
import logging
import json
import string
import argparse
from dotenv import load_dotenv
from guessit import guessit
import hashlib

# Load environment variables from .env file (if present)
load_dotenv()

# Set the TMDB API key from environment variable
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
if not TMDB_API_KEY:
    logging.error("TMDB_API_KEY environment variable is not set.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for verbose logging
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("media_processor.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def sanitize_filename(name):
    """
    Removes or replaces characters that are invalid in filenames.
    
    Args:
        name (str): The original filename.
        
    Returns:
        str: The sanitized filename.
    """
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    sanitized = ''.join(c if c in valid_chars else ' ' for c in name)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized

def parse_movie_filename(filename):
    """
    Extract movie name and year from movie filename using guessit.
    
    Example:
        "Inception.2010.1080p.BluRay.mp4" -> ("Inception", "2010")
    """
    try:
        info = guessit(filename)
        if info.get('type') != 'movie':
            logging.warning(f"File '{filename}' is not identified as a movie.")
            return None, None
        movie_name = info.get('title', '').replace('.', ' ').strip()
        year = str(info.get('year', ''))
        if not movie_name or not year:
            logging.warning(f"Incomplete parsing for movie filename '{filename}'.")
            return None, None
        logging.debug(f"Parsed Movie - Title: {movie_name}, Year: {year}")
        return movie_name, year
    except Exception as e:
        logging.error(f"Error parsing movie filename '{filename}': {e}")
        return None, None

def parse_tv_show_filename(filename):
    """
    Extract show name, season, episode, and episode name from TV show filename using guessit.
    
    Example:
        "Gold.Rush.S13E13.Parkers.Big.Payday.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb.mkv"
        -> ("Gold Rush", "13", "13", "Parkers Big Payday")
    """
    try:
        info = guessit(filename)
        if info.get('type') != 'episode':
            logging.warning(f"File '{filename}' is not identified as a TV show episode.")
            return None, None, None, None
        show_name = info.get('title', '').replace('.', ' ').strip()
        season = str(info.get('season', '0')).zfill(2)
        episode = str(info.get('episode', '0')).zfill(2)
        episode_name = info.get('episode_title', '').replace('.', ' ').strip()
        if not all([show_name, season, episode]):
            logging.warning(f"Incomplete parsing for TV show filename '{filename}'.")
            logging.warning(f"Parsed the following TV Show - Show: {show_name}, Season: {season}, Episode: {episode}, Episode Name: {episode_name}")
            return None, None, None, None
        logging.debug(f"Parsed TV Show - Show: {show_name}, Season: {season}, Episode: {episode}, Episode Name: {episode_name}")
        return show_name, season, episode, episode_name
    except Exception as e:
        logging.error(f"Error parsing TV show filename '{filename}': {e}")
        return None, None, None, None

def is_movie(filename):
    """
    Determine if the file is a movie based on its filename.
    """
    movie_name, year = parse_movie_filename(filename)
    return movie_name is not None and year is not None

def is_tv_show(filename):
    
    """
    Determine if the file is a TV show episode based on its filename.
    """
    show_name, season, episode, episode_name = parse_tv_show_filename(filename)
    return all([show_name, season, episode])

def get_tmdb_headers():
    """
    Returns the headers required for TMDb API requests.
    """
    return {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "Content-Type": "application/json;charset=utf-8"
    }

def get_movie_info(movie_name, year):
    """
    Fetch movie information from TMDb API.
    """
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {
        'query': movie_name,
        'year': year,
        'api_key': TMDB_API_KEY,
        'language': 'en-US'
    }
    try:
        response = requests.get(search_url, params=params, headers=get_tmdb_headers())
        response.raise_for_status()
        data = response.json()
        if data['results']:
            movie_id = data['results'][0]['id']
            movie_info = get_movie_details(movie_id)
            movie_info['media_type'] = '9'
            movie_info['title'] = movie_info['original_title']
            #movie_info['artist'] = ""
            movie_info['description'] = movie_info['overview']
            movie_info['synopsis'] = movie_info['overview']
            print(movie_info)
            cover_art_url = get_movie_cover_art(movie_id)
            return movie_info, cover_art_url
        else:
            logging.warning(f"No results found for movie '{movie_name}' ({year}).")
            return None, None
    except requests.RequestException as e:
        logging.error(f"Error fetching movie info: {e}")
        return None, None

def get_tv_show_info(show_name, season, episode):
    """
    Fetch TV show episode information from TMDb API.
    """
    search_url = "https://api.themoviedb.org/3/search/tv"
    params = {
        'query': show_name,
        'api_key': TMDB_API_KEY,
        'language': 'en-US'
    }
    try:
        response = requests.get(search_url, params=params, headers=get_tmdb_headers())
        response.raise_for_status()
        data = response.json()
        if data['results']:
            show_id = data['results'][0]['id']
            print(data['results'][0])
            episode_info = get_tv_episode_details(show_id, season, episode)
            episode_info['media_type'] = '10'
            episode_info['artist'] = data['results'][0]['name']
            episode_info['sort_artist'] = data['results'][0]['name']
            episode_info['sort_name'] = data['results'][0]['name']
            episode_info['show'] = data['results'][0]['name']
            episode_info['sort_show'] = data['results'][0]['name']
            episode_info['track'] = episode
            episode_info['album_artist'] = data['results'][0]['name']
            episode_info['sort_album_artist'] = data['results'][0]['name']
            episode_info['album'] = data['results'][0]['name'] + ", Season " + season
            episode_info['sort_album'] = data['results'][0]['name'] + ", Season " + season
            episode_info['season_number'] = season
            episode_info['episode_id'] = season + episode
            cover_art_url = get_tv_show_cover_art(show_id)
            return episode_info, cover_art_url
        else:
            logging.warning(f"No results found for TV show '{show_name}'.")
            return None, None
    except requests.RequestException as e:
        logging.error(f"Error fetching TV show info: {e}")
        return None, None

def get_movie_details(movie_id):
    """
    Get detailed movie information from TMDb.
    """
    details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US'
    }
    try:
        response = requests.get(details_url, params=params, headers=get_tmdb_headers())
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching movie details: {e}")
        return None

def get_tv_episode_details(show_id, season, episode):
    """
    Get detailed TV show episode information from TMDb.
    """
    episode_url = f"https://api.themoviedb.org/3/tv/{show_id}/season/{season}/episode/{episode}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US'
    }
    try:
        response = requests.get(episode_url, params=params, headers=get_tmdb_headers())
        response.raise_for_status()
        resp = response.json()
        print(resp)
        ret = {}
        ret['type'] = 'episode'
        ret['title'] = resp.get('name')
        ret['description'] = resp.get('overview')
        ret['date'] = resp.get('air_date')
        #ret['artist'] = resp.get('Show')
        ret['albumn'] = resp.get('season_number')
        ret['track'] = resp.get('episode_number')
        ret['episode_sort'] = resp.get('episode_number')
        return ret
        #return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching TV episode details: {e}")
        return None

def get_movie_cover_art(movie_id):
    """
    Get the best available cover art URL (prioritizing 16:9 backdrops) for the movie.
    """
    images_url = f"https://api.themoviedb.org/3/movie/{movie_id}/images"
    params = {
        'api_key': TMDB_API_KEY
    }
    try:
        response = requests.get(images_url, params=params, headers=get_tmdb_headers())
        response.raise_for_status()
        data = response.json()
        # Prefer backdrops (typically ~16:9)
        if data.get('backdrops'):
            backdrop = data['backdrops'][0]
            return f"https://image.tmdb.org/t/p/w1280{backdrop['file_path']}"
        # Fallback to posters if no backdrops available
        elif data.get('posters'):
            poster = data['posters'][0]
            return f"https://image.tmdb.org/t/p/w1280{poster['file_path']}"
        else:
            logging.warning(f"No cover art available for movie ID {movie_id}.")
            return None
    except requests.RequestException as e:
        logging.error(f"Error fetching movie cover art: {e}")
        return None

def get_tv_show_cover_art(show_id):
    """
    Get the best available cover art URL (prioritizing 16:9 backdrops) for the TV show.
    """
    images_url = f"https://api.themoviedb.org/3/tv/{show_id}/images"
    params = {
        'api_key': TMDB_API_KEY
    }
    try:
        response = requests.get(images_url, params=params, headers=get_tmdb_headers())
        response.raise_for_status()
        data = response.json()
        # Prefer backdrops (typically ~16:9)
        if data.get('backdrops'):
            backdrop = data['backdrops'][0]
            return f"https://image.tmdb.org/t/p/w1280{backdrop['file_path']}"
        # Fallback to posters if no backdrops available
        elif data.get('posters'):
            poster = data['posters'][0]
            return f"https://image.tmdb.org/t/p/w1280{poster['file_path']}"
        else:
            logging.warning(f"No cover art available for TV show ID {show_id}.")
            return None
    except requests.RequestException as e:
        logging.error(f"Error fetching TV show cover art: {e}")
        return None

def download_cover_art(cover_art_url):
    """
    Download cover art to a temporary file with a unique, hashed filename.
    Prioritizes 16:9 cover art by using backdrops first.
    
    Args:
        cover_art_url (str): URL of the cover art image.
    
    Returns:
        str: Path to the downloaded cover art image.
    """
    if not cover_art_url:
        logging.warning("No cover art URL provided.")
        return None

    try:
        # Create a unique hash using the cover_art_url and process ID
        pid = os.getpid()
        hash_input = f"{cover_art_url}-{pid}".encode('utf-8')
        hash_digest = hashlib.sha256(hash_input).hexdigest()
        file_extension = os.path.splitext(cover_art_url)[1] or '.jpg'
        temp_dir = tempfile.gettempdir()
        temp_filename = f"cover_art_{hash_digest}{file_extension}"
        temp_path = os.path.join(temp_dir, temp_filename)

        # Download the image
        logging.debug(f"Downloading cover art from '{cover_art_url}' to '{temp_path}'.")
        response = requests.get(cover_art_url, stream=True)
        response.raise_for_status()
        with open(temp_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        logging.info(f"Cover art downloaded to '{temp_path}'.")
        return temp_path
    except requests.RequestException as e:
        logging.error(f"Error downloading cover art from '{cover_art_url}': {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error downloading cover art: {e}")
        return None

def embed_metadata_with_ffmpeg(source_path, destination_path, metadata, cover_art_path=None, subtitle_streams=[]):
    """
    Embed metadata, cover art, and subtitles into the media file using ffmpeg.
    
    Args:
        source_path (Path): Path to the source media file.
        destination_path (Path): Path where the processed file will be saved.
        metadata (dict): Dictionary containing metadata fields.
        cover_art_path (str): Path to the cover art image.
        subtitle_streams (list): List of subtitle streams to embed.
    """
    try:
        cmd = ['ffmpeg', '-i', str(source_path)]
        
        # Add cover art if available
        if cover_art_path and os.path.exists(cover_art_path):
            cmd.extend(['-i', str(cover_art_path)])  # Input cover art image
        
        # Initialize mapping and codec options
        map_options = []
        codec_options = []

        # Map video and audio streams
        map_options.extend(['-map', '0:v:0'])
        map_options.extend(['-map', '0:a:0'])

        # If cover art is present, map it
        if cover_art_path and os.path.exists(cover_art_path):
            map_options.extend(['-map', '1:v:0'])
            # Copy video and audio streams
            codec_options.extend(['-c:v:0', 'copy', '-c:a:0', 'copy'])
            codec_options.extend(["-tag:v:0", "hvc1"])  # Add HEVC tag for compatibility
            # Encode cover art
            codec_options.extend(['-c:v:1', 'mjpeg', '-disposition:v:1', 'attached_pic'])
        else:
            # If no cover art, copy video and audio directly
            codec_options.extend(['-c:v', 'copy', '-c:a', 'copy'])
            codec_options.extend(["-tag:v", "hvc1"])  # Add HEVC tag for compatibility

        

        # Embed subtitles
        for idx, subtitle in enumerate(subtitle_streams):
            codec = subtitle['codec_name'].lower()
            if codec in ['subrip', 'mov_text']:
                map_options.extend(['-map', f'0:s:{idx}'])
                codec_options.extend([f'-c:s:{idx}', 'mov_text']) #codec
            else:
                logging.warning(f"Unsupported subtitle codec '{codec}' at stream index {subtitle['index']}. Skipping.")
        # Combine all options
        cmd.extend(map_options)
        cmd.extend(codec_options)
        
        # Add metadata
        for key, value in metadata.items():
            cmd.extend(['-metadata', f'{key}={value}'])
        
        # Overwrite output file without prompt
        cmd.extend(['-y', str(destination_path)])
        print(cmd)
        if cover_art_path and os.path.exists(cover_art_path):
            print(f"Running FFMPEG command with cover art: {' '.join(cmd)}")
            logging.debug(f"Running FFMPEG command with cover art: {' '.join(cmd)}")
        else:
            print(f"Running FFMPEG command without cover art: {' '.join(cmd)}")
            logging.debug(f"Running FFMPEG command without cover art: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logging.info(f"Embedded metadata into '{destination_path}'.")
    except subprocess.CalledProcessError as e:
        logging.error(f"ffmpeg failed: {e}")
    except Exception as e:
        logging.error(f"Error embedding metadata: {e}")

def process_file(source_path, destination_path, file_ext, metadata, cover_art_path=None, subtitle_streams=[]):
    """
    Process a single media file: embed metadata, cover art, and subtitles.
    
    Args:
        source_path (Path): Path to the source media file.
        destination_path (Path): Path where the processed file will be saved.
        file_ext (str): File extension (e.g., '.mp4', '.mkv').
        metadata (dict): Metadata to embed.
        cover_art_path (str): Path to the cover art image.
        subtitle_streams (list): List of subtitle streams to embed.
    """
    logging.info(f"Processing file '{source_path}'...")
    destination_path = destination_path.with_suffix('.mp4')
    embed_metadata_with_ffmpeg(source_path, destination_path, metadata, cover_art_path, subtitle_streams)
    logging.info(f"File '{source_path}' processed successfully.")

def get_subtitle_streams(media_file):
    """
    Retrieve subtitle streams from the media file.
    
    Args:
        media_file (Path): Path to the media file.
    
    Returns:
        list: List of subtitle stream dictionaries.
    """
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 
               'stream=index,codec_name', '-of', 'json', str(media_file)]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        return data.get('streams', [])
    except subprocess.CalledProcessError as e:
        logging.error(f"ffprobe failed for '{media_file}': {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding ffprobe output for '{media_file}': {e}")
        return []

def process_directory(input_dir, output_base_dir):
    """
    Recursively processes all .mp4 and .mkv files within the given directory.
    
    :param input_dir: Path to the input directory.
    :param output_base_dir: Base directory where processed files will be stored.
    """
    input_path = Path(input_dir)
    output_base_path = Path(output_base_dir)

    # Recursively search for .mp4 and .mkv files
    if input_path.is_dir():
        media_files = list(input_path.rglob('*.[Mm][Pp]4')) + list(input_path.rglob('*.[Mm][Kk][Vv]'))
    else:
        media_files = [input_path]

    if not media_files:
        logging.info(f"No .mp4 or .mkv files found in directory '{input_dir}'.")
        return

    for media_file in media_files:
        try:
            filename = media_file.name
            file_ext = media_file.suffix.lower()

            if is_movie(filename):
                # Movie processing
                movie_name, year = parse_movie_filename(filename)
                if not all([movie_name, year]):
                    logging.error(f"Failed to parse movie details from filename '{filename}'. Skipping.")
                    continue

                # Build the destination directory: Movies/Movie Name/
                destination_dir = output_base_path / "Movies" / sanitize_filename(movie_name)
                destination_dir.mkdir(parents=True, exist_ok=True)

                # Format the new filename: 'Movie Name.mp4'
                new_filename = f"{sanitize_filename(movie_name)}{file_ext}"
                destination_file = destination_dir / new_filename

                # Retrieve metadata and cover art
                movie_info, cover_art_url = get_movie_info(movie_name, year)
                if not movie_info:
                    logging.error(f"Failed to retrieve movie information for '{movie_name}'. Skipping.")
                    continue

                cover_art_path = download_cover_art(cover_art_url)
                subtitle_streams = get_subtitle_streams(media_file)

                # Process the file
                process_file(media_file, destination_file, file_ext, movie_info, cover_art_path, subtitle_streams)

                # Clean up temporary cover art file
                if cover_art_path:
                    os.remove(cover_art_path)

            elif is_tv_show(filename):
                # TV show processing using guessit
                show_name, season, episode, episode_name = parse_tv_show_filename(filename)
                if not all([show_name, season, episode]):
                    logging.error(f"Failed to parse TV show details from filename '{filename}'. Skipping.")
                    continue

                # Build the destination directory: TV/Show Name/Season XX/
                destination_dir = output_base_path / "TV Shows" / sanitize_filename(show_name) / f"Season {season}"
                destination_dir.mkdir(parents=True, exist_ok=True)

                # Format the new filename: 'XX Episode Name.mp4'
                new_filename = f"{episode.zfill(2)} {sanitize_filename(episode_name)}{file_ext}"
                destination_file = destination_dir / new_filename

                # Retrieve metadata and cover art
                tv_info, cover_art_url = get_tv_show_info(show_name, season, episode)
                print(tv_info)
                if not tv_info:
                    logging.error(f"Failed to retrieve TV show information for '{show_name}'. Skipping.")
                    continue

                cover_art_path = download_cover_art(cover_art_url)
                subtitle_streams = get_subtitle_streams(media_file)

                # Process the file
                process_file(media_file, destination_file, file_ext, {'type': 'episode', **tv_info}, cover_art_path, subtitle_streams)

                # Clean up temporary cover art file
                if cover_art_path:
                    os.remove(cover_art_path)

            else:
                logging.warning(f"Could not determine media type for file '{filename}'. Skipping.")
        except Exception as e:
            logging.error(f"An error occurred while processing '{media_file}': {e}")

def main():
    parser = argparse.ArgumentParser(description="Process and organize media files with embedded metadata.")
    parser.add_argument('input_path', type=str, help='Path to the media file or directory containing media files.')
    parser.add_argument('output_directory', type=str, help='Directory where processed files will be saved.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging.')
    parser.add_argument('--printInfo', action='store_true', help='Print movie or TV show information.')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    input_path = args.input_path
    output_directory = args.output_directory

    input_path_obj = Path(input_path)
    
    if args.printInfo:
        if input_path_obj.is_file():
            filename = input_path_obj.name
            if is_movie(filename):
                movie_name, year = parse_movie_filename(filename)
                movie_info, _ = get_movie_info(movie_name, year)
                if movie_info:
                    print(movie_info)
            elif is_tv_show(filename):
                show_name, season, episode, _ = parse_tv_show_filename(filename)
                tv_info, _ = get_tv_show_info(show_name, season, episode)
                if tv_info:
                    print(tv_info)
        else:
            logging.error("printInfo requires a single media file as input")
            sys.exit(1)
    elif input_path_obj.is_dir() or input_path_obj.is_file():
        # Process directory with batch processing
        process_directory(input_path_obj, Path(output_directory))
    else:
        logging.error(f"Input path '{input_path}' is neither a file nor a directory.")
        sys.exit(1)

def print_tv_show_info(data):
    # Print TV show episode information
    logging.info(f"Name: {data.get('name')}")
    logging.info(f"Air Date: {data.get('air_date')}")
    logging.info(f"Overview: {data.get('overview')}")

def print_movie_info(data):
    # Print movie information
    logging.info(f"Title: {data.get('title')}")
    logging.info(f"Original Title: {data.get('original_title')}")
    logging.info(f"Release Date: {data.get('release_date')}")
    logging.info(f"Runtime: {data.get('runtime')} minutes")
    logging.info(f"Genres: {', '.join([genre['name'] for genre in data.get('genres', [])])}")
    logging.info(f"Director: {'N/A'}")  # TMDb requires additional requests to get directors from credits
    logging.info(f"Actors: {'N/A'}")     # TMDb requires additional requests to get actors from credits
    logging.info(f"Plot: {data.get('overview')}")
    logging.info(f"TMDb Rating: {data.get('vote_average')}")

def get_media_info(file_path):
    """Get media information for a file."""
    try:
        filename = Path(file_path).name
        if is_movie(filename):
            movie_name, year = parse_movie_filename(filename)
            if movie_name and year:
                movie_info, _ = get_movie_info(movie_name, year)
                if movie_info:
                    return (f"Type: Movie\n"
                           f"Title: {movie_info.get('title', 'N/A')}\n"
                           f"Year: {year}\n"
                           f"Description: {movie_info.get('description', 'N/A')}")
        elif is_tv_show(filename):
            show_name, season, episode, episode_name = parse_tv_show_filename(filename)
            if all([show_name, season, episode]):
                tv_info, _ = get_tv_show_info(show_name, season, episode)
                if tv_info:
                    return (f"Type: TV Show\n"
                           f"Show: {tv_info.get('show', 'N/A')}\n"
                           f"Season: {season}\n"
                           f"Episode: {episode}\n"
                           f"Title: {tv_info.get('title', 'N/A')}\n"
                           f"Description: {tv_info.get('description', 'N/A')}")
        return "Could not determine media type or fetch information"
    except Exception as e:
        return f"Error getting media info: {str(e)}"

def convert_file(file_path, output_base_dir):
    """Convert a media file with proper metadata."""
    try:
        source_path = Path(file_path)
        output_base_path = Path(output_base_dir)
        filename = source_path.name
        
        if is_movie(filename):
            movie_name, year = parse_movie_filename(filename)
            yield f"Converting movie: {movie_name}...."
            if movie_name and year:
                destination_dir = output_base_path / "Movies" / sanitize_filename(movie_name)
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination_file = destination_dir / f"{sanitize_filename(movie_name)}.mp4"
                
                movie_info, cover_art_url = get_movie_info(movie_name, year)
                if movie_info:
                    cover_art_path = download_cover_art(cover_art_url)
                    subtitle_streams = get_subtitle_streams(source_path)
                    process_file(source_path, destination_file, source_path.suffix, movie_info, cover_art_path, subtitle_streams)
                    if cover_art_path:
                        os.remove(cover_art_path)
                    yield f"complete\n"
                    return f"Successfully converted movie: {movie_name}"
                
        elif is_tv_show(filename):
            show_name, season, episode, episode_name = parse_tv_show_filename(filename)
            yield f"Converting tv show: {show_name}: S{season}E{episode}..."
            if all([show_name, season, episode]):
                destination_dir = output_base_path / "TV Shows" / sanitize_filename(show_name) / f"Season {season}"
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination_file = destination_dir / f"{episode.zfill(2)} {sanitize_filename(episode_name or 'Episode ' + episode)}.mp4"
                
                tv_info, cover_art_url = get_tv_show_info(show_name, season, episode)
                if tv_info:
                    cover_art_path = download_cover_art(cover_art_url)
                    subtitle_streams = get_subtitle_streams(source_path)
                    process_file(source_path, destination_file, source_path.suffix, {'type': 'episode', **tv_info}, cover_art_path, subtitle_streams)
                    if cover_art_path:
                        os.remove(cover_art_path)
                    yield f"complete\n"
                    return f"Successfully converted episode: {show_name} S{season}E{episode}"
        
        return "Could not convert file: unable to determine media type or fetch information"
    except Exception as e:
        return f"Error converting file: {str(e)}"

if __name__ == '__main__':
    main()
