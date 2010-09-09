package nl.jteam.search.solrext.spatial.function;

import nl.jteam.search.solrext.spatial.FieldValueSource;
import nl.jteam.search.solrext.spatial.FieldValueSourceRegistry;
import org.apache.lucene.queryParser.ParseException;
import org.apache.solr.common.util.NamedList;
import org.apache.solr.search.FunctionQParser;
import org.apache.solr.search.ValueSourceParser;
import org.apache.solr.search.function.ValueSource;

public class DistanceValueSourceParser extends ValueSourceParser {
  public void init(NamedList namedList) {

  }

  public ValueSource parse(FunctionQParser fqp) throws ParseException {
    String distanceField = fqp.parseArg();
    FieldValueSource valueSource = FieldValueSourceRegistry.getRegistryFromRequest(fqp.getReq()).getSource(distanceField);
    if(valueSource == null) {
//          throw new IllegalStateException("DistanceValueSourceParser uses distance calculated by " +
//              "SpatialTierQueryParser. Please check your query and try again.");
      return null;
    }
    return new DistanceValueSource(distanceField, valueSource);
  }
}
