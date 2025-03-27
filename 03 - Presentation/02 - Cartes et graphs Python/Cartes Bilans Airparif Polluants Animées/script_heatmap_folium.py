import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMapWithTime
from folium.plugins import TimestampedGeoJson
from datetime import datetime, timedelta
import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account


def creer_heatmap_no2(fichier_donnees, fichier_coordonnees, chemin_sortie="map_no2.html"):
    """
    Crée une heatmap animée des concentrations de NO2 à Paris
    
    Args:
        fichier_donnees (str): Chemin vers le fichier Excel avec les données nettoyées
        fichier_coordonnees (str): Chemin vers le fichier CSV/JSON avec les coordonnées des capteurs
        chemin_sortie (str, optional): Chemin pour sauvegarder la carte HTML
    """
    print(f"Création d'une heatmap à partir de {fichier_donnees}...")
    
    # Charger les données nettoyées
    df = pd.read_excel(fichier_donnees)
    
    # Charger les coordonnées des capteurs
    ext = os.path.splitext(fichier_coordonnees)[1].lower()
    if ext == '.csv':
        coords = pd.read_csv(fichier_coordonnees)
    elif ext == '.json':
        with open(fichier_coordonnees, 'r') as f:
            coords = pd.DataFrame(json.load(f))
    else:
        raise ValueError(f"Format de fichier de coordonnées non pris en charge: {ext}")
    
    # Vérifier que les colonnes nécessaires sont présentes dans les coordonnées
    colonnes_requises = ['capteur', 'lat', 'lon']
    for col in colonnes_requises:
        if col not in coords.columns:
            raise ValueError(f"Le fichier de coordonnées doit contenir une colonne '{col}'")
    
    # Définir les positions des capteurs
    capteurs = {row['capteur']: (row['lat'], row['lon']) for _, row in coords.iterrows()}
    
    # Vérifier que tous les capteurs des données existent dans le fichier de coordonnées
    colonnes_temps = ['Date complète', 'Année', 'Mois', 'Heure']
    colonnes_capteurs = [col for col in df.columns if col not in colonnes_temps]
    
    capteurs_manquants = [capteur for capteur in colonnes_capteurs if capteur not in capteurs]
    if capteurs_manquants:
        print(f"Attention: Les capteurs suivants n'ont pas de coordonnées: {capteurs_manquants}")
        print("Ces capteurs seront exclus de la visualisation.")
    
    # Filtrer pour ne garder que les capteurs avec des coordonnées
    colonnes_capteurs = [capteur for capteur in colonnes_capteurs if capteur in capteurs]
    
    if not colonnes_capteurs:
        raise ValueError("Aucun capteur avec des coordonnées n'a été trouvé.")
    
    # Convertir les données pour la visualisation avec Folium
    # Regrouper par jour pour avoir une animation plus fluide
    df['Date complète'] = pd.to_datetime(df['Date complète'])
    df['date'] = df['Date complète'].dt.date
    
    # Calculer les moyennes quotidiennes
    df_daily = df.groupby('date')[colonnes_capteurs].mean().reset_index()
    
    # Préparer les données pour HeatMapWithTime
    dates = df_daily['date'].unique()
    heatmap_data = []
    
    for date in dates:
        daily_data = []
        day_values = df_daily[df_daily['date'] == date]
        
        for capteur in colonnes_capteurs:
            if capteur in capteurs:
                lat, lon = capteurs[capteur]
                value = day_values[capteur].values[0]
                
                # Normaliser la valeur pour la heatmap (0-1)
                # Utiliser une échelle logarithmique pour mieux visualiser les différences
                normalized_value = np.log1p(value) / 10  # Ajuster selon la plage de vos données
                
                # Ajouter les coordonnées et la valeur
                daily_data.append([lat, lon, normalized_value])
        
        heatmap_data.append(daily_data)
    
    # Créer une carte centrée sur Paris
    m = folium.Map(location=[48.8566, 2.3522], zoom_start=12, tiles='CartoDB positron')
    
    # Ajouter les marqueurs de position des capteurs
    for capteur, (lat, lon) in capteurs.items():
        if capteur in colonnes_capteurs:
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                color='black',
                fill=True,
                fill_color='black',
                fill_opacity=0.7,
                popup=capteur
            ).add_to(m)
    
    # Créer une légende pour la carte
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: 120px; 
                border:2px solid grey; z-index:9999; background-color:white;
                padding: 10px;">
        <h4 style="margin-top: 0;">Concentration NO2</h4>
        <div style="display: flex; flex-direction: column; height: 60px; justify-content: space-between;">
            <div>
                <span style="display: inline-block; width: 15px; height: 15px; background-color: red;"></span>
                <span style="margin-left: 5px;">Élevée</span>
            </div>
            <div>
                <span style="display: inline-block; width: 15px; height: 15px; background-color: yellow;"></span>
                <span style="margin-left: 5px;">Moyenne</span>
            </div>
            <div>
                <span style="display: inline-block; width: 15px; height: 15px; background-color: green;"></span>
                <span style="margin-left: 5px;">Faible</span>
            </div>
        </div>
    </div>
    '''
    
    # Ajouter la légende à la carte
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Formater les dates pour l'affichage
    date_labels = [date.strftime("%d %b %Y") for date in dates]
    
    # Ajouter la heatmap avec animation temporelle
    HeatMapWithTime(
        heatmap_data,
        index=date_labels,
        auto_play=True,
        radius=20,
        gradient={
            0.2: 'green',
            0.5: 'yellow',
            0.8: 'orange',
            1.0: 'red'
        },
        min_opacity=0.5,
        max_opacity=0.8,
        use_local_extrema=False
    ).add_to(m)
    
    # Sauvegarder la carte
    print(f"Sauvegarde de la carte: {chemin_sortie}")
    m.save(chemin_sortie)
    print("Carte créée avec succès!")
    
    return m

# Exemple d'utilisation
if __name__ == "__main__":

    credpath = os.path.join("credentials", "artefact-da53-projet-final-b60d2589fda1.json")
    # définition des credentials Google en variable d'environnement en pointant vers la clé du compte de service Google
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credpath
    # préparation et définition des credentials du compte de service Google en pointant vers la clé JSON et en définissant les scopes d'action : drive (on a des tables à base de Google Sheets), cloud plateform, et bigquery.
    credentials = service_account.Credentials.from_service_account_file(credpath,  scopes=["https://www.googleapis.com/auth/drive","https://www.googleapis.com/auth/cloud-platform","https://www.googleapis.com/auth/bigquery"])
   
    # préparation du client bigquery avec appel à la fonction Client, en faisant passer les infos de credentials définies plus haut.
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)
    # préparation de la requête SQL qui sera utilisée dans bigquery
    query = """SELECT *
            FROM `artefact-da53-projet-final.04_AirQuality.2014_AirQuality_NO2_Clean`"""
    # récupération dans une dataframe des résultats de la requête BQ
    df = client.query(query).to_dataframe()

    # Exemples de chemins de fichiers (à ajuster selon votre configuration)
    fichier_donnees = df
    
    # Exemple de contenu pour le fichier de coordonnées (à créer)
    # Voici des coordonnées approximatives pour les capteurs (à remplacer par les vraies coordonnées)
    coordonnees_exemple = {
        "capteur": ["PA15L", "OPERA", "BP_EST", "BASCH", "BONAP", "CELES", "EIFF3", "ELYS", "PA07", "PA12", "PA13", "PA18", "HAUS", "PA4", "AUT", "SOULT"],
        "lat": [48.8417, 48.8713, 48.8652, 48.8372, 48.8675, 48.8536, 48.8582, 48.8699, 48.8577, 48.8409, 48.8269, 48.8921, 48.8796, 48.8559, 48.8350, 48.8360],
        "lon": [2.3008, 2.3326, 2.4101, 2.2690, 2.3368, 2.3669, 2.2944, 2.3155, 2.2980, 2.4154, 2.3593, 2.3526, 2.3429, 2.3635, 2.4020, 2.4100]
    }
    
    # Sauvegarder les coordonnées dans un fichier JSON temporaire
    import json
    with open("coordonnees_capteurs.json", "w") as f:
        json.dump(coordonnees_exemple, f)
    
    # Créer la heatmap
    creer_heatmap_no2(fichier_donnees, "coordonnees_capteurs.json")