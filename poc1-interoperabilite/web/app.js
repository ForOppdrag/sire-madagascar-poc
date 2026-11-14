/* SIRE — démonstrateur d'interopérabilité (POC 1)
 * Chaque couche illustre un niveau d'intégration :
 *   - répliquée et harmonisée dans le SIRE, diffusée par GeoServer (WMS)
 *   - consultée à la source chez un producteur simulé (OGC API - Features)
 *   - décrite dans le catalogue (OGC API - Records)
 */
(function () {
  'use strict';

  const NIVEAUX = ['Catalogué', 'Consultable', 'Exposé', 'Répliqué et harmonisé', 'Référence'];
  const MADAGASCAR = ol.proj.transformExtent([43.0, -25.8, 50.7, -11.8], 'EPSG:4326', 'EPSG:3857');

  // Échappement systématique de toute donnée affichée (protection XSS, OWASP A03)
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const wms = (couche) => new ol.layer.Image({
    source: new ol.source.ImageWMS({
      url: '/geoserver/sire/wms',
      params: { LAYERS: couche, FORMAT: 'image/png', TRANSPARENT: true },
      ratio: 1, serverType: 'geoserver', crossOrigin: 'anonymous',
    }),
  });

  const pointsEau = new ol.layer.Vector({
    source: new ol.source.Vector({
      url: '/producteur/collections/points_eau/items?f=json&limit=5000',
      format: new ol.format.GeoJSON({ featureProjection: 'EPSG:3857' }),
    }),
    style: (f) => new ol.style.Style({
      image: new ol.style.Circle({
        radius: 5,
        fill: new ol.style.Fill({ color: f.get('fonctionnel') === 'oui' ? '#2BB3A3' : '#F2A541' }),
        stroke: new ol.style.Stroke({ color: '#0B3C5D', width: 1 }),
      }),
    }),
  });

  const couches = [
    { id: 'regions', titre: 'Régions (COD-AB)', niveau: 4, couche: wms('sire:regions') },
    { id: 'bassins', titre: 'Bassins versants (HydroBASINS)', niveau: 3, couche: wms('sire:bassins') },
    { id: 'rivieres', titre: 'Cours d\'eau (HydroRIVERS)', niveau: 3, couche: wms('sire:rivieres') },
    { id: 'points', titre: 'Points d\'eau — producteur simulé, lus à la source', niveau: 2, couche: pointsEau },
  ];

  const carte = new ol.Map({
    target: 'carte',
    layers: [new ol.layer.Tile({ source: new ol.source.OSM() }), ...couches.map((c) => c.couche)],
    view: new ol.View({ center: ol.extent.getCenter(MADAGASCAR), zoom: 5 }),
  });
  carte.getView().fit(MADAGASCAR, { padding: [20, 20, 20, 20] });

  // Panneau des couches
  const liste = document.getElementById('couches');
  couches.forEach((c) => {
    const li = document.createElement('li');
    li.innerHTML = `<input type="checkbox" id="c-${esc(c.id)}" checked>
      <label for="c-${esc(c.id)}">${esc(c.titre)}<br>
      <span class="badge n${c.niveau}">Niveau ${c.niveau} — ${esc(NIVEAUX[c.niveau])}</span></label>`;
    li.querySelector('input').addEventListener('change', (e) => c.couche.setVisible(e.target.checked));
    liste.appendChild(li);
  });

  // Interrogation : points (vecteur) puis bassins (WMS GetFeatureInfo)
  const info = document.getElementById('info');
  const tableau = (props) => '<table>' + Object.entries(props)
    .filter(([k]) => k !== 'geometry')
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('') + '</table>';

  carte.on('singleclick', async (evt) => {
    const f = carte.forEachFeatureAtPixel(evt.pixel, (x) => x);
    if (f) { info.innerHTML = '<strong>Point d\'eau (producteur simulé)</strong>' + tableau(f.getProperties()); return; }
    const url = couches[1].couche.getSource().getFeatureInfoUrl(
      evt.coordinate, carte.getView().getResolution(), 'EPSG:3857',
      { INFO_FORMAT: 'application/json', QUERY_LAYERS: 'sire:bassins' });
    try {
      const r = await fetch(url);
      const j = await r.json();
      info.innerHTML = j.features && j.features.length
        ? '<strong>Bassin versant (base du SIRE)</strong>' + tableau(j.features[0].properties)
        : 'Aucun objet à cet endroit.';
    } catch (e) { info.textContent = 'Service indisponible.'; }
  });

  // Recherche dans le catalogue (OGC API - Records)
  const resultats = document.getElementById('resultats');
  async function chercher(q) {
    const params = new URLSearchParams({ f: 'json', limit: '50' });
    if (q) params.set('q', q);
    try {
      const r = await fetch(`/catalogue/collections/jeux_donnees/items?${params}`);
      const j = await r.json();
      resultats.innerHTML = (j.features || []).map((rec) => {
        const p = rec.properties;
        return `<li><strong>${esc(p.title)}</strong>
          <span class="badge n${esc(p.niveau_integration)}">Niveau ${esc(p.niveau_integration)} — ${esc(p.niveau_integration_libelle)}</span>
          <small>${esc((p.contacts || [])[0]?.name)}</small></li>`;
      }).join('') || '<li>Aucun résultat.</li>';
    } catch (e) { resultats.innerHTML = '<li>Catalogue indisponible.</li>'; }
  }
  document.getElementById('recherche').addEventListener('submit', (e) => {
    e.preventDefault(); chercher(document.getElementById('q').value.trim());
  });
  chercher('');
})();
