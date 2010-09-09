package nl.jteam.search.solrext.spatial;

import nl.jteam.search.solrext.spatial.lucene.DistanceFieldComparatorSource;
import nl.jteam.search.solrext.spatial.lucene.SpatialFilter;
import nl.jteam.search.solrext.spatial.lucene.geometry.ArcDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.geometry.GeoDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.geometry.PlaneGeoDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;
import org.apache.lucene.queryParser.ParseException;
import org.apache.lucene.search.FilteredQuery;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.Sort;
import org.apache.lucene.search.SortField;
import org.apache.solr.common.SolrException;
import org.apache.solr.common.params.CommonParams;
import org.apache.solr.common.params.SolrParams;
import org.apache.solr.common.util.NamedList;
import org.apache.solr.request.SolrQueryRequest;
import org.apache.solr.schema.SchemaField;
import org.apache.solr.search.QParser;
import org.apache.solr.search.QParserPlugin;
import org.apache.solr.search.SortSpec;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;

import static nl.jteam.search.solrext.spatial.SpatialParams.*;

/**
 * SpatialTierQueryParserPlugin is responsible to instantiating and configuring instances of {@link SpatialTierQParser},
 * the QParser responsible for processing spatial queries.  It can be configured as follows in the solrconfig.xml:
 * <pre>
 * &lt;queryParser name="spatial" class="nl.jteam.search.solrext.spatial.SpatialTierQueryParserPlugin">
 *      &lt;str name="corePoolSize"&gt;1&lt;/str&gt;
 *      &lt;str name="maxPoolSize"&gt;2&lt;/str&gt;
 *      &lt;str name="keepAlive"&gt;60&lt;/str&gt;
 *  &lt;/queryParser&gt;
 * </pre>
 *
 * The parser accepts a number of properties which control how the underlying multi-threaded distance filtering works:
 * <ol>
 * <li>corePoolSize - How many threads will be kept in the Executor pool by default.
 * <li>maxPoolSize - Maximum number of threads in Executor pool.
 * <li>keepAlive - how long idle theads will be kept in pool when the number of threads is higher then core pool size.
 * </ol>
 * <p/>
 *
 * The Plugin also accepts a "basedOn" property which defines the QParser type that should be used to parse the non-spatial
 * part of the query.
 */
public class SpatialTierQueryParserPlugin extends QParserPlugin {

    public static final String NAME = "spatial_tier";

    private static Pattern sortSep = Pattern.compile(",");

    private String basedOn;
    private String latFieldName;
    private String lngFieldName;
    private String tierPrefixName;
    private ExecutorService executorService;

    /**
     * {@inheritDoc}
     */
    public void init(NamedList args) {
        basedOn = retrieveValueFromNamedList(args, "basedOn", QParserPlugin.DEFAULT_QTYPE);
        latFieldName = retrieveValueFromNamedList(args, LAT_FIELD_KEY, LAT_FIELD_DEFAULT);
        lngFieldName = retrieveValueFromNamedList(args, LNG_FIELD_KEY, LNG_FIELD_DEFAULT);
        tierPrefixName = retrieveValueFromNamedList(args, TIER_FIELD_KEY, TIER_FIELD_DEFAULT);
        executorService = buildExecutorService(args);
    }

    /**
     * {@inheritDoc}
     */
    public QParser createParser(String qstr, SolrParams localParams, SolrParams params, SolrQueryRequest req) {
        return new SpatialTierQParser(qstr, localParams, params, req);
    }

    /**
     * Returns an <code>ExecutorService</code> configured with values from the specified arguments.
     *
     * @param arguments The list of arguments containing the corePoolSize, maxPoolSize and keepAlive
     * @return an <code>ExecutorService</code> configured with values from the specified arguments
     * @throws NumberFormatException If corePoolSize, maxPoolSize or keepAlive is missing in the specified arguments list
     */
    private ExecutorService buildExecutorService(NamedList arguments) {
        int corePoolSize = Integer.parseInt((String) arguments.get("corePoolSize"));
        int maxPoolSize = Integer.parseInt((String) arguments.get("maxPoolSize"));
        int keepAlive = Integer.parseInt((String) arguments.get("keepAlive"));
        BlockingDeque<Runnable> queue = new LinkedBlockingDeque<Runnable>();
        RejectedExecutionHandler handler = new ThreadPoolExecutor.CallerRunsPolicy();
        return new ThreadPoolExecutor(corePoolSize, maxPoolSize, keepAlive, TimeUnit.SECONDS, queue, new DaemonThreadFactory(), handler);
    }

    /**
     * Returns the value in the name list with the specified key or returns the specified defaultValue when the value
     * for the specified name is <code>null</code>.
     *
     * @param namedList The named list containing a value for the specified key
     * @param key The key that contains a value
     * @param defaultValue The value to return if the value for the specified key is <code>null</code>
     * @return a value in namedList for the specified key or the specified defaultValue when value is <code>null</code>
     */
    private String retrieveValueFromNamedList(NamedList namedList, String key, String defaultValue) {
        String value = (String) namedList.get(key);
        return value != null ? value : defaultValue;
    }

    // ================================================= Inner Classes =================================================

    /**
     * The <code>SpatialTierQParser</code> main responsibility is constructing the <code>SpatialFilter</code> based
     * on the incoming query string. There are a number of properties that can be set:
     * <ul>
     * <li> The threadCount. How many threads are used for the distance calculation. The default is one.
     * <li> The latitude of the current search
     * <li> The longitude of the current search
     * <li> The radius of the current search
     * </ul>
     * All the properties are configured via the local params.
     *
     * @see SpatialTierUpdateProcessorFactory
     */
    private class SpatialTierQParser extends QParser {

        private final SpatialFilter spatialFilter;
        private final Query preConstructedQuery;

        public SpatialTierQParser(String queryString, SolrParams localParams, SolrParams params, SolrQueryRequest request) {
            super(queryString, localParams, params, request);

            validateRequest(localParams);

            QParserPlugin parserPlugin = request.getCore().getQueryPlugin(basedOn);
            QParser parser = parserPlugin.createParser(queryString, localParams, params, request);
            try {
                preConstructedQuery = parser.getQuery();
            } catch (ParseException pe) {
                throw new RuntimeException(pe);
            }

            int threadCount = localParams.getInt(THREAD_COUNT_KEY, 1);
            double latitude = Double.parseDouble(localParams.get(LAT));
            double longitude = Double.parseDouble(localParams.get(LNG));
            double radius = Double.parseDouble(localParams.get(RADIUS));

            DistanceUnit distanceUnit = DistanceUnit.findDistanceUnit(localParams.get(UNIT, DistanceUnit.MILES.getUnit()));
            GeoDistanceCalculator distanceCalculator = resolveGeoDistanceCalculator(localParams.get(CALC, ARC_CALC_PARAM));

            spatialFilter = new SpatialFilter(
                    latitude,
                    longitude,
                    radius,
                    distanceUnit,
                    latFieldName,
                    lngFieldName,
                    tierPrefixName,
                    distanceCalculator,
                    executorService,
                    threadCount,
                    preConstructedQuery);

            String distanceField = params.get(DISTANCE_FIELD_KEY, DISTANCE_FIELD_DEFAULT);
            FieldValueSourceRegistry.registerFieldValueSource(request, new DistanceFieldValueSource(spatialFilter, distanceField));
        }

        /**
         * {@inheritDoc}
         */
        public Query parse() throws ParseException {
            return new FilteredQuery(preConstructedQuery, spatialFilter);
        }


        // -------------------------------------------- Helper Methods -------------------------------------------------

        /**
         * This method is overriden to support sorting on distance.
         * <p/>
         * {@inheritDoc}
         */
        public SortSpec getSort(boolean useGlobalParams) throws ParseException {
            getQuery(); // ensure query is parsed first

            String sortStr = null;
            String startS = null;
            String rowsS = null;

            if (localParams != null) {
                sortStr = localParams.get(CommonParams.SORT);
                startS = localParams.get(CommonParams.START);
                rowsS = localParams.get(CommonParams.ROWS);

                // if any of these parameters are present, don't go back to the global params
                if (sortStr != null || startS != null || rowsS != null) {
                    useGlobalParams = false;
                }
            }

            if (useGlobalParams) {
                sortStr = params.get(CommonParams.SORT);
                startS = params.get(CommonParams.START);
                rowsS = params.get(CommonParams.ROWS);
            }

            int start = startS != null ? Integer.parseInt(startS) : 0;
            int rows = rowsS != null ? Integer.parseInt(rowsS) : 10;

            Sort sort = null;
            if (sortStr != null) {
                sort = parseSort(sortStr);
            }
            return new SortSpec(sort, start, rows);
        }

        /**
         * Copy of {@link org.apache.solr.search.QueryParsing#parseSort(String, org.apache.solr.schema.IndexSchema)}
         * that adds in support for sorting on the distance field (however it is referred to in the request).
         *
         * @param sortSpec Sort spec to parse
         * @return Sort representing the sort requirements specified in the sort spec
         */
        protected Sort parseSort(String sortSpec) {
            String distanceField = params.get(DISTANCE_FIELD_KEY, DISTANCE_FIELD_DEFAULT);
            
            if (sortSpec == null || sortSpec.length() == 0) {
                return null;
            }

            String[] parts = sortSep.split(sortSpec.trim());
            if (parts.length == 0) {
                return null;
            }

            SortField[] lst = new SortField[parts.length];
            for (int i = 0; i < parts.length; i++) {
                String part = parts[i].trim();
                boolean top = true;

                int idx = part.indexOf(' ');
                if (idx > 0) {
                    String order = part.substring(idx + 1).trim();
                    if ("desc".equals(order) || "top".equals(order)) {
                        top = true;
                    } else if ("asc".equals(order) || "bottom".equals(order)) {
                        top = false;
                    } else {
                        throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "Unknown sort order: " + order);
                    }
                    part = part.substring(0, idx).trim();
                } else {
                    throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "Missing sort order.");
                }

                if ("score".equals(part)) {
                    if (top) {
                        if (parts.length == 1) {
                            return null;
                        }
                        lst[i] = SortField.FIELD_SCORE;
                    } else {
                        lst[i] = new SortField(null, SortField.SCORE, true);
                    }
                } else if ("#".equals(part)) {
                    lst[i] = new SortField(null, SortField.DOC, top);
                } else if (distanceField.equals(part)) {
                    lst[i] = new SortField(distanceField, new DistanceFieldComparatorSource(spatialFilter.getDistanceFilter()), top);
                } else {
                    try {
                        SchemaField field = req.getSchema().getField(part);
                        if (field == null || !field.indexed()) {
                            throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "can not sort on unindexed field: " + part);
                        }
                        lst[i] = field.getType().getSortField(field, top);
                    } catch (SolrException sse) {
                        throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "can not sort on undefined field: " + part, sse);
                    }
                }
            }
            return new Sort(lst);
        }
        
        /**
         * Resolves the GeoDistanceCalculator to use based on the values in the given params.  If the specified calculator
         * is unknown, a {@link org.apache.solr.common.SolrException} is thrown.
         *
         * @param calcParam SolrParams to resolve the calculator from
         * @return GeoDistanceCalculator refered to by the {@link SpatialParams#CALC} parameter
         *         in the local params.
         */
        private GeoDistanceCalculator resolveGeoDistanceCalculator(String calcParam) {
            if (ARC_CALC_PARAM.equals(calcParam)) {
                return new ArcDistanceCalculator();
            }

            if (PLANE_CALC_PARAM.equals(calcParam)) {
                return new PlaneGeoDistanceCalculator();
            }

            throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "Unknown distance calculator " + calcParam);
        }

        /**
         * Checks that the required parameters for a spatial search are in the given SolrParams
         *
         * @param params SolrParams to check if it contains the required parameters
         */
        private void validateRequest(SolrParams params) {
            String latitude = params.get(LAT);
            if (latitude == null) {
                throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "Latitude parameter is missing");
            }

            String longitude = params.get(LNG);
            if (longitude == null) {
                throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "Longitude parameter is missing");
            }

            String radius = params.get(RADIUS);
            if (radius == null) {
                throw new SolrException(SolrException.ErrorCode.BAD_REQUEST, "Radius parameter is missing");
            }
        }
    }

    /**
     * Simple implementation of {@link ThreadFactory} that simulates the default ThreadFactory behavior while ensuring
     * that all threads have {@link Thread#setDaemon(boolean)} to true, ensuring they do not prevent application servers
     * from closing cleanly.
     */
    private static class DaemonThreadFactory implements ThreadFactory {

        private static final AtomicInteger poolNumber = new AtomicInteger(1);
        private final ThreadGroup group;
        private final AtomicInteger threadNumber = new AtomicInteger(1);
        private final String namePrefix;

        private DaemonThreadFactory() {
            SecurityManager manager = System.getSecurityManager();
            group = (manager != null) ? manager.getThreadGroup() : Thread.currentThread().getThreadGroup();
            namePrefix = "pool-" + poolNumber.getAndIncrement() + "-thread-";
        }

        public Thread newThread(Runnable runnable) {
            Thread thread = new Thread(group, runnable, namePrefix + threadNumber.getAndIncrement(), 0);
            thread.setDaemon(true);
            if (thread.getPriority() != Thread.NORM_PRIORITY) {
                thread.setPriority(Thread.NORM_PRIORITY);
            }
            return thread;
        }
    }
}
