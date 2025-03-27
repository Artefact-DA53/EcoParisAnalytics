import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from google.cloud import bigquery
import pandas as pd

def authenticate_google_drive():
    """Authentification avec Google Drive API."""
    # Chemin vers votre fichier d'identifiants (à remplacer par votre chemin)
    credentials_path = '/home/tonychamcham/EcoParisAnalytics/credentials/artefact-da53-projet-final-b60d2589fda1.json'
    
    # Définir les scopes nécessaires
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    # Créer les credentials
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES)
    
    # Construire le service Drive
    drive_service = build('drive', 'v3', credentials=credentials)
    
    return drive_service

def list_files_and_folders(drive_service, folder_id):
    """Liste tous les fichiers et sous-dossiers dans un dossier Google Drive."""
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="nextPageToken, files(id, name, mimeType)"
    ).execute()
    
    items = results.get('files', [])
    return items

def download_file(drive_service, file_id, file_name):
    """Télécharge un fichier depuis Google Drive."""
    request = drive_service.files().get_media(fileId=file_id)
    
    # Créer un objet pour stocker le contenu du fichier
    file_io = io.BytesIO()
    downloader = MediaIoBaseDownload(file_io, request)
    
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Téléchargement {int(status.progress() * 100)}%")
    
    # Revenir au début du flux
    file_io.seek(0)
    
    # Créer un dossier temporaire pour stocker les fichiers téléchargés
    if not os.path.exists('temp_files'):
        os.makedirs('temp_files')
    
    # Sauvegarder le fichier localement
    local_file_path = os.path.join('temp_files', file_name)
    with open(local_file_path, 'wb') as f:
        f.write(file_io.read())
    
    return local_file_path

def upload_to_bigquery(file_path, dataset_id, table_id):
    """Upload un fichier CSV vers BigQuery."""
    # Initialiser le client BigQuery
    client = bigquery.Client()
    
    # Définir la table de destination
    table_ref = client.dataset(dataset_id).table(table_id)
    
    # Charger le fichier CSV avec pandas
    df = pd.read_csv(file_path)
    
    # Configurer le job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE  # Écrase la table si elle existe déjà
    )
    
    # Charger les données dans BigQuery
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    
    # Attendre que le job se termine
    job.result()
    
    print(f"Chargé {job.output_rows} lignes dans {dataset_id}.{table_id}")

def get_valid_table_name(file_name):
    """Convertit un nom de fichier en nom de table BigQuery valide."""
    # Supprimer l'extension .csv
    base_name = os.path.splitext(file_name)[0]
    
    # Remplacer les caractères non valides par des underscores
    valid_name = ''.join(c if c.isalnum() else '_' for c in base_name)
    
    # S'assurer que le nom commence par une lettre ou un underscore
    if not valid_name[0].isalpha() and valid_name[0] != '_':
        valid_name = 'table_' + valid_name
    
    return valid_name

def process_folder(drive_service, folder_id, folder_path, dataset_id):
    """Traite récursivement un dossier et ses sous-dossiers."""
    items = list_files_and_folders(drive_service, folder_id)
    
    for item in items:
        item_name = item['name']
        item_id = item['id']
        
        # Créer un chemin d'accès pour l'item
        item_path = folder_path + '/' + item_name if folder_path else item_name
        
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            # C'est un dossier, donc on l'explore récursivement
            print(f"Exploration du dossier: {item_path}")
            process_folder(drive_service, item_id, item_path, dataset_id)
        
        elif item_name.lower().endswith('.csv'):
            # C'est un fichier CSV, donc on le traite
            print(f"Traitement du fichier CSV: {item_path}")
            
            # Télécharger le fichier
            local_file_path = download_file(drive_service, item_id, item_name)
            
            # Créer un nom de table valide basé sur le chemin du fichier
            # Remplacer les / par des _ pour inclure la hiérarchie des dossiers
            table_path = item_path.replace('/', '_')
            table_id = get_valid_table_name(table_path)
            
            # Upload vers BigQuery avec un nom de table unique
            try:
                upload_to_bigquery(local_file_path, dataset_id, table_id)
            except Exception as e:
                print(f"Erreur lors de l'upload de {item_path}: {str(e)}")
            
            # Supprimer le fichier local après upload
            os.remove(local_file_path)

def main():
    # ID du dossier Google Drive racine
    root_folder_id = '1ZPndbEXrv1PUnw_BJx4K5V1YCmNAawgv'
    
    # ID du dataset BigQuery
    dataset_id = '06_RAWdata_AirQuality'
    
    # Authentification avec Google Drive
    drive_service = authenticate_google_drive()
    
    # Traiter tous les dossiers de manière récursive
    process_folder(drive_service, root_folder_id, "", dataset_id)
    
    print("Traitement terminé.")

if __name__ == '__main__':
    main()
