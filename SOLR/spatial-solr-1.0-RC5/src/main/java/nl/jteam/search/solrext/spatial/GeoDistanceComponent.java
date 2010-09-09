package nl.jteam.search.solrext.spatial;

import org.apache.solr.handler.component.ResponseBuilder;
import org.apache.solr.handler.component.SearchComponent;
import org.apache.solr.common.SolrDocumentList;
import org.apache.solr.common.SolrDocument;
import org.apache.solr.util.SolrPluginUtils;
import org.apache.lucene.document.Fieldable;

import java.io.IOException;
import java.util.Map;
import java.util.HashMap;

/**
 * SearchComponent that handles any post-processing of the distance calculations made through the
 * {@link SpatialTierQueryParserPlugin} and {@link nl.jteam.search.solrext.spatial.lucene.SpatialFilter}.
 * Currently the only processing that occurs is that the calculated distances are added to the search results
 * <p/>
 * Note that this component assumes that results existing within the ResponseBuilder when
 * {@link #process(org.apache.solr.handler.component.ResponseBuilder)} is executed.  Therefore this component should be
 * added after {@link org.apache.solr.handler.component.QueryComponent} in the components for your RequestHandlers.
 *  
 * @author Chris Male
 */
public class GeoDistanceComponent extends SearchComponent {

    /**
     * {@inheritDoc}
     */
    public void prepare(ResponseBuilder responseBuilder) throws IOException {
        // No preparation required
    }

    /**
     * Adds in the calculated distances to the search results
     *
     * {@inheritDoc}
     */
    public void process(ResponseBuilder responseBuilder) throws IOException {
        String distanceField = responseBuilder.req.getParams().get(SpatialParams.DISTANCE_FIELD_KEY, SpatialParams.DISTANCE_FIELD_DEFAULT);
        FieldValueSource valueSource = FieldValueSourceRegistry.getRegistryFromRequest(responseBuilder.req).getSource(distanceField);

        if (valueSource == null) {
            return;
        }
        
        if (responseBuilder.getResults() == null) {
            throw new IllegalStateException("GeoDistanceComponent uses existing query results.  However none have be " +
                    "included in the response.  Please add this component after a query component");
        }

        Map<SolrDocument, Integer> idsByDocument = new HashMap<SolrDocument, Integer>();
        SolrDocumentList documentList = SolrPluginUtils.docListToSolrDocumentList(
            responseBuilder.getResults().docList,
            responseBuilder.req.getSearcher(),
            responseBuilder.rsp.getReturnFields(),
            idsByDocument);

        for (SolrDocument document : documentList) {
            Fieldable[] values = valueSource.getValues(idsByDocument.get(document));
            if (values != null) {
                double distance = Double.parseDouble(values[0].stringValue());
                document.addField(distanceField, distance);
            }
        }

        responseBuilder.rsp.getValues().remove("response");
        responseBuilder.rsp.add("response", documentList);
    }

    // ============================================ SolrInfoMBeans methods =============================================

    /**
     * {@inheritDoc}
     */
    public String getDescription() {
        return "Includes the calculated distances in the search results";
    }

    /**
     * {@inheritDoc}
     */
    public String getSourceId() {
        return null;
    }

    /**
     * {@inheritDoc}
     */
    public String getSource() {
        return "GeoDistanceComponent.java";
    }

    /**
     * {@inheritDoc}
     */
    public String getVersion() {
        return null;
    }
}
