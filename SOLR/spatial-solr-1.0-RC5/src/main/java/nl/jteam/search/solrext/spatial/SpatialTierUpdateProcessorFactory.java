package nl.jteam.search.solrext.spatial;

import static nl.jteam.search.solrext.spatial.SpatialParams.*;
import nl.jteam.search.solrext.spatial.lucene.tier.CartesianTierPlotter;
import nl.jteam.search.solrext.spatial.lucene.tier.projection.Projector;
import nl.jteam.search.solrext.spatial.lucene.tier.projection.SinusoidalProjector;
import org.apache.lucene.util.NumericUtils;
import org.apache.solr.common.SolrInputDocument;
import org.apache.solr.common.params.SolrParams;
import org.apache.solr.common.util.NamedList;
import org.apache.solr.request.SolrQueryRequest;
import org.apache.solr.request.SolrQueryResponse;
import org.apache.solr.update.AddUpdateCommand;
import org.apache.solr.update.processor.UpdateRequestProcessor;
import org.apache.solr.update.processor.UpdateRequestProcessorFactory;

import java.io.IOException;
import java.util.LinkedList;
import java.util.List;

/**
 * Factory for {@link SpatialTierUpdateProcessor} instances.
 *
 * The SpatialTierUpdateProcessor is responsible for adding Cartesian tier boxes to the documents before adding them to
 * the index. In order to give the document the proper tier information the following is needed:
 * <ul>
 *  <li>The name of the field that contains latitude information. The default is {@link SpatialParams#LAT_FIELD_DEFAULT}.
 *  <li>The name of the field that contains longitude information. The default is {@link SpatialParams#LNG_FIELD_DEFAULT}.
 *  <li>The prefix that should be given to the fields created by the Processor. The default is {@link SpatialParams#TIER_FIELD_DEFAULT}
 *  <li>The ID of the first cartesian tier level. The default is 6.
 *  <li>The ID of the last cartesian tier level. The default is 14.
 * </ul>
 *
 * Each tier level will have its own field in a document. So by default 8 fields will be added with _field_[level] as name.
 * <p/>
 * An example of how the ProcessorFactory should be configured in the solrconfig.xml is:
 * <pre>
 * &lt;updateRequestProcessorChain&gt;
 *       &lt;processor class="nl.jteam.search.solrext.SpatialTierUpdateProcessorFactory"&gt;
 *           &lt;str name="latField"&gt;lat&lt;/str&gt;
 *           &lt;str name="lngField"&gt;lng&lt;/str&gt;
 *           &lt;int name="startTier"&gt;9&lt;/int&gt;
 *           &lt;int name="endTier"&gt;17&lt;/int&gt;
 *       &lt;/processor&gt;
 *       &lt;processor class="solr.LogUpdateProcessorFactory"/&gt;
 *     &lt;processor class="solr.RunUpdateProcessorFactory"/&gt;
 *   &lt;/updateRequestProcessorChain&gt;
 * </pre>
 */
public class SpatialTierUpdateProcessorFactory extends UpdateRequestProcessorFactory {

    private List<CartesianTierPlotter> cartesianTierPlotters = new LinkedList<CartesianTierPlotter>();
    private Projector sinusoidalProjector = new SinusoidalProjector();

    private String latField;
    private String lngField;
    private String tierPrefix;

    private int cartesianStartTierLevel = 6;
    private int cartesianEndTierLevel = 14;

    /**
     * {@inheritDoc}
     */
    @Override
    public void init(NamedList args) {
        super.init(args);
        if (args != null) {
            SolrParams params = SolrParams.toSolrParams(args);
            latField = params.get(LAT_FIELD_KEY, LAT_FIELD_DEFAULT);
            lngField = params.get(LNG_FIELD_KEY, LNG_FIELD_DEFAULT);
            tierPrefix = params.get(TIER_FIELD_KEY, TIER_FIELD_DEFAULT);
            cartesianStartTierLevel = params.getInt("startTier", cartesianStartTierLevel);
            cartesianEndTierLevel = params.getInt("endTier", cartesianEndTierLevel);
        }

        for (int i = cartesianStartTierLevel; i < cartesianEndTierLevel; i++) {
            cartesianTierPlotters.add(new CartesianTierPlotter(i, sinusoidalProjector));
        }
    }

    /**
     * {@inheritDoc}
     */
    public UpdateRequestProcessor getInstance(SolrQueryRequest request, SolrQueryResponse response, UpdateRequestProcessor next) {
        return new SpatialTierUpdateProcessor(next, tierPrefix);
    }

    // ============================================= Inner Classes =====================================================

    /**
     * SpatialTierUpdateProcessor adds in Cartesian Tier information to documents based on their latitude and longitude
     */
    private class SpatialTierUpdateProcessor extends UpdateRequestProcessor {

        private final String tierPrefix;

        /**
         * Creates a new SpatialTierUpdateProcessor that adds fields with the given prefix, to Documents
         *
         * @param next Next UpdateRequestProcessor in the processing chain
         * @param tierPrefix Prefix to be given to fields added that contain cartesian tier information 
         */
        public SpatialTierUpdateProcessor(UpdateRequestProcessor next, String tierPrefix) {
            super(next);
            this.tierPrefix = tierPrefix;
        }

        /**
         * {@inheritDoc}
         */
        @Override
        public void processAdd(AddUpdateCommand cmd) throws IOException {
            SolrInputDocument document = cmd.getSolrInputDocument();

            Object lat = document.getFieldValue(latField);
            Object lng = document.getFieldValue(lngField);

            if (lat != null && lng != null) {
                for (CartesianTierPlotter tierPlotter : cartesianTierPlotters) {
                    document.addField(
                            tierPrefix + tierPlotter.getTierLevelId(),
                            NumericUtils.doubleToPrefixCoded(tierPlotter.getTierBoxId(Double.parseDouble(lat.toString()), Double.parseDouble(lng.toString()))));
                }
            }
            super.processAdd(cmd);
        }
    }
}