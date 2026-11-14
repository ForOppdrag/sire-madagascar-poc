<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>sire_rivieres</Name>
    <UserStyle>
      <Title>Cours d'eau</Title>
      <FeatureTypeStyle>
        <Rule>
          <ogc:Filter><ogc:PropertyIsLessThan><ogc:PropertyName>ord_stra</ogc:PropertyName><ogc:Literal>5</ogc:Literal></ogc:PropertyIsLessThan></ogc:Filter>
          <LineSymbolizer><Stroke><CssParameter name="stroke">#1C7293</CssParameter><CssParameter name="stroke-width">0.6</CssParameter></Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>ord_stra</ogc:PropertyName><ogc:Literal>5</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>
          <LineSymbolizer><Stroke><CssParameter name="stroke">#1C7293</CssParameter><CssParameter name="stroke-width">1.2</CssParameter></Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <ogc:Filter><ogc:PropertyIsGreaterThan><ogc:PropertyName>ord_stra</ogc:PropertyName><ogc:Literal>5</ogc:Literal></ogc:PropertyIsGreaterThan></ogc:Filter>
          <LineSymbolizer><Stroke><CssParameter name="stroke">#1C7293</CssParameter><CssParameter name="stroke-width">2.2</CssParameter></Stroke></LineSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
