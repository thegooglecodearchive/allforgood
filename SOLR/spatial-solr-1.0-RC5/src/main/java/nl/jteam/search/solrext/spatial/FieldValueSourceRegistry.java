package nl.jteam.search.solrext.spatial;

import org.apache.solr.request.SolrQueryRequest;

import java.util.Map;
import java.util.HashMap;

/**
 * FieldValueSourceRegistry provides a structured place for FieldValueSources to be stored whule they are part of a
 * SolrQueryRequest's context.
 * <p/>
 * Ideally the FieldValueSources should be registered in a {@link org.apache.solr.handler.component.ResponseBuilder},
 * however due to the limitations of the current API, ResponseBuilders are not always available at places where a
 * FieldValueSource might be registered.  Consequently FieldValueSources must be stored in the context of SolrQueryRequests,
 * which are always available.  Rather than just adding the sources to the context, a FieldValueSourceRegistry exists
 * within the context so that the sources can be added and retrieved in a structured way.
 * <p/>
 * It should be noted that for simplicity the FieldValueSourceRegistry is not thread-safe.
 *
 * @author Chris Male
 */
public class FieldValueSourceRegistry {

    private final static String REQUEST_CONTEXT_KEY = "__fieldValueSourceRegistry";

    private final Map<String, FieldValueSource> fieldValueSourceByField = new HashMap<String, FieldValueSource>();

    /**
     * Returns the FieldValueSource, if any, that is registered for the given field name.  If no FieldValueSource is registered,
     * {@code null} is returned.
     *
     * @param fieldName Name of the field whose FieldValueSource should be retrived
     * @return FieldValueSource registered for the field, or {@code null} if none is registered
     */
    public FieldValueSource getSource(String fieldName) {
        return fieldValueSourceByField.get(fieldName);
    }

    /**
     * Registers the given FieldValueSource.  If a FieldValueSource already exists for the field the new one applies to,
     * then the existing is overwritten
     *
     * @param fieldValueSource FieldValueSource to register
     */
    public void registerFieldValueSource(FieldValueSource fieldValueSource) {
        fieldValueSourceByField.put(fieldValueSource.getFieldName(), fieldValueSource);
    }

    /**
     * Registers the given FieldValueSource in the registry contained in the given SolrQueryRequest
     *
     * @param request SolrQueryRequest containing the registry where the source should be registered
     * @param fieldValueSource FieldValueSource to register
     */
    public static void registerFieldValueSource(SolrQueryRequest request, FieldValueSource fieldValueSource) {
        FieldValueSourceRegistry registry = getRegistryFromRequest(request);
        registry.registerFieldValueSource(fieldValueSource);
    }

    /**
     * Retrieves the FieldValueSourceRegistry contained in the given SolrQueryRequest.  Note, if no registry is found,
     * one is created and added to the request.
     *
     * @param request SolrQueryRequest whose FieldValueSourceRegistry should be retrieved
     * @return FieldValueSourceRegistry contained in the request
     */
    public static FieldValueSourceRegistry getRegistryFromRequest(SolrQueryRequest request) {
        FieldValueSourceRegistry registry = (FieldValueSourceRegistry) request.getContext().get(REQUEST_CONTEXT_KEY);
        if (registry == null) {
            registry = new FieldValueSourceRegistry();
            request.getContext().put(REQUEST_CONTEXT_KEY, registry);
        }
        return registry;
    }
}
