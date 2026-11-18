# Données (non versionnées)

`data/raw` et `data/processed` sont des liens symboliques vers le disque externe :

- `/media/dell/Transcend1/nisar_data/raw/{sentinel1,nisar,biomass,sentinel2}`
- `/media/dell/Transcend1/nisar_data/processed/{sentinel1,nisar,sentinel2,comparaison}`

Recréer les liens sur une autre machine :

```bash
ln -sfn /chemin/vers/nisar_data/raw data/raw
ln -sfn /chemin/vers/nisar_data/processed data/processed
```
