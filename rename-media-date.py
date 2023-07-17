from PIL import Image
import os
import datetime
import glob
import sys
import re
import argparse
import shutil
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

def filename_has_match(directory, filename):
    # Get the filename without any leading timestamp
    filename_without_timestamp = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_", "", filename)

    # Loop through files in the directory
    for file in os.listdir(directory):
        # Get the file name without any leading timestamp
        file_without_timestamp = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_", "", file)
        
        # Check if the filenames match (disregarding timestamps)
        if filename_without_timestamp == file_without_timestamp:
            return True

    return False

def get_media_creation_date(media_path):
    try:
        if media_path.lower().endswith(".mp4"):
            parser = createParser(media_path)
            if not parser:
                raise ValueError("Unable to parse the MP4 file.")
                
            metadata = extractMetadata(parser)
            if metadata is None:
                raise ValueError("Unable to extract metadata from the MP4 file.")
                
            # Get the creation date from the MP4 metadata
            media_creation_date = metadata.get("creation_date")
            if not media_creation_date:
                raise ValueError("Media creation date not found in the metadata.")
            
            # Convert the creation date to a datetime object if it's not already
            if not isinstance(media_creation_date, datetime.datetime):
                media_creation_date = datetime.datetime.strptime(media_creation_date, "%Y-%m-%dT%H:%M:%S")
            
            return media_creation_date
        else:
            image = Image.open(media_path)
            exif_data = image._getexif()
            if exif_data is not None and 36867 in exif_data:
                date_taken = exif_data[36867]
                return datetime.datetime.strptime(date_taken, "%Y:%m:%d %H:%M:%S")
            else:
                return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def has_timestamp_in_filename(filename):
    # Regular expression pattern to match timestamps at the beginning of the filename
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_"
    return re.search(pattern, filename) is not None

def sanitize_filename(filename):
    # Replace invalid characters with hyphens
    return re.sub(r'[<>:"/\\|?*]', '-', filename)

def save_media_with_datetime(original_path, media_creation_date, destination_dir=None, adjust_hours=0, simulate=False, force=False):
    if media_creation_date is None:
        print(f"{original_path} - File does not contain creation date in metadata.")
        return False

    adjusted_datetime = media_creation_date + datetime.timedelta(hours=adjust_hours)

    original_dir, original_filename = os.path.split(original_path)
    if not original_dir:
        original_dir = "."
        
    filename, extension = os.path.splitext(original_filename)

    # If a source file already has a timestamp, remove it before continuing to avoid multiple timestamps
    if has_timestamp_in_filename(filename):
        filename_components = filename.split("_")
        filename_components.pop(0)

        filename = '_'.join(filename_components)

    new_filename = f"{adjusted_datetime.isoformat()}_{filename}{extension}"
    sanitized_new_filename = sanitize_filename(new_filename)

    if destination_dir is None:
        target_dir = original_dir
    else:
        target_dir = destination_dir

    new_path = os.path.join(target_dir, sanitized_new_filename)

    # If the force copy option is enabled, proceed to copy. Otherwise, 
    # skip copying if the file already exists in the destination directory with the same filename
    if not force and (os.path.exists(new_path) or filename_has_match(target_dir, sanitized_new_filename)):
        # File with the same name (ignoring timestamps) already exists, skip copying
        # print(f"Skipped: {original_path} (File with similar name already exists in the destination directory)")
        return False

    if not simulate:
        # Copy the file to the destination directory
        shutil.copy2(original_path, new_path)
        print(f"{original_path} -> {new_path} - Copied")
    else:
        print(f"{original_path} -> {new_path} - Simulated Copy")

    return True

def process_media(file_spec, destination_dir=None, adjust_hours=0, simulate=False, force=False):
    total_media_requested = 0
    total_media_processed = 0
    total_media_without_dates = 0

    media_files = glob.glob(file_spec)

    if len(media_files) == 0:
        print("No matching media files found.")
        return

    for media_file in media_files:
        total_media_requested += 1

        media_creation_date = get_media_creation_date(media_file)
        if media_creation_date is not None:
            if save_media_with_datetime(media_file, media_creation_date, destination_dir, adjust_hours, simulate, force):
                total_media_processed += 1
        else:
            total_media_without_dates += 1
            print(f"{media_file} - File does not contain the creation date in metadata")

    print(f"\nInput Media: {total_media_requested}, Processed: {total_media_processed}, Already Copied: {total_media_requested - total_media_processed - total_media_without_dates}, No Creation Date: {total_media_without_dates}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename media files with date and time taken/created.")
    parser.add_argument("file_spec", help="Input file specification (e.g., *.jpg or *.mp4)")
    parser.add_argument("destination_dir", nargs="?", default=None, help="Destination directory for renamed files")
    parser.add_argument("-s", "--simulate", action="store_true", help="Simulate or preview the renaming process")
    parser.add_argument("-a", "--adjust", type=int, default=0, help="Adjust photo taken/created time by specified hours (negative numbers subtract hours)")
    parser.add_argument("--force", action="store_true", help="Force copy files to destination even if they already exist with the target name or with the same name and a different timestamp")
    args = parser.parse_args()

    process_media(args.file_spec, args.destination_dir, args.adjust, args.simulate, args.force)
