"""Fiche de métadonnées ISO 19115 encodée en ISO 19139 (XML), version minimale.

Elle suffit pour alimenter un catalogue CSW (pycsw, GeoNetwork) et rendre un
jeu de données « catalogué » (niveau d'intégration 0).
"""

from __future__ import annotations

import uuid
from datetime import date
from xml.sax.saxutils import escape

from .profiler import Profil

GABARIT = """<?xml version="1.0" encoding="UTF-8"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd"
                 xmlns:gco="http://www.isotc211.org/2005/gco"
                 xmlns:gml="http://www.opengis.net/gml">
  <gmd:fileIdentifier><gco:CharacterString>{identifiant}</gco:CharacterString></gmd:fileIdentifier>
  <gmd:language><gmd:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/" codeListValue="fre">fre</gmd:LanguageCode></gmd:language>
  <gmd:hierarchyLevel><gmd:MD_ScopeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset">dataset</gmd:MD_ScopeCode></gmd:hierarchyLevel>
  <gmd:contact>
    <gmd:CI_ResponsibleParty>
      <gmd:organisationName><gco:CharacterString>{organisation}</gco:CharacterString></gmd:organisationName>
      <gmd:role><gmd:CI_RoleCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_RoleCode" codeListValue="pointOfContact">pointOfContact</gmd:CI_RoleCode></gmd:role>
    </gmd:CI_ResponsibleParty>
  </gmd:contact>
  <gmd:dateStamp><gco:Date>{date_fiche}</gco:Date></gmd:dateStamp>
  <gmd:metadataStandardName><gco:CharacterString>ISO 19115:2003/19139</gco:CharacterString></gmd:metadataStandardName>
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification>
      <gmd:citation>
        <gmd:CI_Citation>
          <gmd:title><gco:CharacterString>{titre}</gco:CharacterString></gmd:title>
          <gmd:date><gmd:CI_Date>
            <gmd:date><gco:Date>{date_fiche}</gco:Date></gmd:date>
            <gmd:dateType><gmd:CI_DateTypeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_DateTypeCode" codeListValue="revision">revision</gmd:CI_DateTypeCode></gmd:dateType>
          </gmd:CI_Date></gmd:date>
        </gmd:CI_Citation>
      </gmd:citation>
      <gmd:abstract><gco:CharacterString>{resume}</gco:CharacterString></gmd:abstract>
      <gmd:descriptiveKeywords><gmd:MD_Keywords>
{mots_cles}
      </gmd:MD_Keywords></gmd:descriptiveKeywords>
      <gmd:language><gmd:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/" codeListValue="fre">fre</gmd:LanguageCode></gmd:language>
      <gmd:topicCategory><gmd:MD_TopicCategoryCode>inlandWaters</gmd:MD_TopicCategoryCode></gmd:topicCategory>
{etendue}
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
  <gmd:dataQualityInfo>
    <gmd:DQ_DataQuality>
      <gmd:scope><gmd:DQ_Scope><gmd:level><gmd:MD_ScopeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset">dataset</gmd:MD_ScopeCode></gmd:level></gmd:DQ_Scope></gmd:scope>
      <gmd:lineage><gmd:LI_Lineage><gmd:statement><gco:CharacterString>{lignee}</gco:CharacterString></gmd:statement></gmd:LI_Lineage></gmd:lineage>
    </gmd:DQ_DataQuality>
  </gmd:dataQualityInfo>
</gmd:MD_Metadata>
"""

ETENDUE = """      <gmd:extent><gmd:EX_Extent>
        <gmd:geographicElement><gmd:EX_GeographicBoundingBox>
          <gmd:westBoundLongitude><gco:Decimal>{o}</gco:Decimal></gmd:westBoundLongitude>
          <gmd:eastBoundLongitude><gco:Decimal>{e}</gco:Decimal></gmd:eastBoundLongitude>
          <gmd:southBoundLatitude><gco:Decimal>{s}</gco:Decimal></gmd:southBoundLatitude>
          <gmd:northBoundLatitude><gco:Decimal>{n}</gco:Decimal></gmd:northBoundLatitude>
        </gmd:EX_GeographicBoundingBox></gmd:geographicElement>
      </gmd:EX_Extent></gmd:extent>"""


def fiche_iso19139(p: Profil, titre: str, organisation: str, resume: str = "",
                   mots_cles: list[str] | None = None, identifiant: str | None = None) -> str:
    mots = mots_cles or ["eau", "Madagascar", "SIRE"]
    kw = "\n".join(f"        <gmd:keyword><gco:CharacterString>{escape(m)}</gco:CharacterString></gmd:keyword>" for m in mots)
    etendue = ""
    if p.emprise:
        o, s, e, n = p.emprise
        etendue = ETENDUE.format(o=o, e=e, s=s, n=n)
    lignee = (f"Profil automatique : {p.nb_lignes} objets, complétude {p.taux_completude_global:.0%}, "
              f"score de qualité indicatif {p.score_qualite}/100. Alertes : "
              + ("; ".join(p.alertes) if p.alertes else "aucune") + ".")
    return GABARIT.format(
        identifiant=escape(identifiant or str(uuid.uuid4())), organisation=escape(organisation),
        date_fiche=date.today().isoformat(), titre=escape(titre),
        resume=escape(resume or f"Jeu de données {titre}."), mots_cles=kw, etendue=etendue,
        lignee=escape(lignee),
    )
