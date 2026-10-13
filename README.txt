ZHONX III — Mécanique

Projet mécanique du robot ZHONX III, migré de SolidWorks vers FreeCAD.

Ouvrir FreeCAD_ZHONX_III/ZHONX_III.FCStd dans FreeCAD (vérifié avec 1.1.3).
Ce fichier contient l'assemblage principal autonome, avec 81 occurrences.
Le guide d'utilisation détaillé est FreeCAD_ZHONX_III/LISEZ_MOI.txt.

La conversion comprend 33 pièces reconstruites avec esquisses et fonctions
Part Design, 11 composants conservés comme solides importés et 13 assemblages.
Les contraintes de conception et d'assemblage SolidWorks ne sont pas transférées.
Les 58 documents FreeCAD se recalculent sans erreur ; les 33 reconstructions
ont été comparées aux références STEP, avec un écart maximal échantillonné
de 0,000579 mm. Les rapports de vérification accompagnent les modèles.

Les 71 fichiers natifs SolidWorks (pièces, assemblages, plans et un ancien
fichier sans extension) ont été retirés. Les modèles FreeCAD, les références
STEP et le manifeste d'assemblage suffisent aux contrôles et à la reconstruction.
Les scripts d'extraction restent disponibles pour une éventuelle réutilisation
avec une copie externe des sources, via leur option --source.

Autres dossiers conservés :
  Modelisation_ZHONX_III : exports historiques STL, DXF, PDF et VRML uniquement.
  Engrenages_Plans : plans PDF des engrenages.
  Zhonx_III_Cambam : projets et fichiers d'usinage historiques.
  Datasheets, Capteurs, Composants, Procedures, Labyrinthe : documentation.
  Image_SW : images historiques du modèle avant migration.

Ces exports et fichiers d'usinage historiques ne sont pas automatiquement
régénérés lors de la modification d'une pièce FreeCAD.

Contrôle local, depuis FreeCAD_ZHONX_III, avec le Python fourni par FreeCAD :
  /Applications/FreeCAD.app/Contents/Resources/bin/python tools/check_project.py

L'extracteur tiers inclus dans FreeCAD_ZHONX_III/tools/vendor/sldprt2step
est sous licence Apache 2.0 ; sa licence et ses avis d'origine sont fournis.
