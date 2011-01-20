/*
 * Copyright (c) 2009 JTeam B.V.
 * www.jteam.nl
 * All rights reserved.
 *
 * This software is the confidential and proprietary information of
 * JTeam B.V. ("Confidential Information").
 * You shall not disclose such Confidential Information and shall use
 * it only in accordance with the terms of the license agreement you
 * entered into with JTeam.
 */

package nl.jteam.search.solrext.spatial;

import org.apache.solr.util.AbstractSolrTestCase;
import org.apache.solr.util.SolrPluginUtils;
import org.apache.solr.request.SolrQueryRequest;
import org.apache.solr.request.SolrQueryResponse;
import org.apache.solr.common.SolrInputDocument;
import org.apache.solr.common.SolrDocumentList;
import org.apache.solr.update.AddUpdateCommand;
import org.apache.solr.search.DocList;
import org.apache.solr.search.SolrIndexSearcher;

import java.io.IOException;
import java.util.List;

/**
 * Intergration Tests of the geo searching functionality from a Solr level
 * 
 * @author Martijn van Groningen
 * @since Sep 28, 2009
 */
public class SpatialTierIntegrationTest extends AbstractSolrTestCase {

    public String getSchemaFile() {
        return "schema-tier.xml";
    }

    public String getSolrConfigFile() {
        return "solrconfig-tier.xml";
    }

    /* Pass condition: two result are returned out of the four in the index */
    public void testGeoSearch() throws Exception {
        addToIndex("id", "1", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "2", "lat", "52.3554", "lng", "4.8323", "name", "Slotervaart en Overtoomse Veld");
        addToIndex("id", "3", "lat", "50.8715", "lng", "6.03231", "name", "Kamps Nederland Limburg");
        addToIndex("id", "4", "lat", "50.947", "lng", "5.78302", "name", "Preuve Limburg");
        assertU(commit());

        SolrQueryRequest req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km}*:*", "qt", "standard");
        SolrQueryResponse response = h.queryAndResponse("standard", req);
        SolrDocumentList solrDocumentList = retrieveResponseDocuments(response);
        assertEquals(2, solrDocumentList.size());
        assertEquals("1", solrDocumentList.get(0).getFieldValue("id"));
        assertEquals("2", solrDocumentList.get(1).getFieldValue("id"));
    }

    /* Pass condition: three result is returned out of the four in the index. This is for a bugfix in ThreadedDistanceFilter */
    public void testGeoSearch_notEvenBugfix() throws Exception {
        addToIndex("id", "1", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "2", "lat", "50.8715", "lng", "6.03231", "name", "Kamps Nederland Limburg");
        addToIndex("id", "3", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "4", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        assertU(commit());

        SolrQueryRequest req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km threadCount=2}*:*", "qt", "standard");
        SolrQueryResponse response = h.queryAndResponse("standard", req);
        SolrDocumentList solrDocumentList = retrieveResponseDocuments(response);
        assertEquals(3, solrDocumentList.size());
        assertEquals("1", solrDocumentList.get(0).getFieldValue("id"));
        assertEquals("3", solrDocumentList.get(1).getFieldValue("id"));
        assertEquals("4", solrDocumentList.get(2).getFieldValue("id"));
    }

    /* Pass condition: Sorting on the field geo_distance should succeed as the parsing of the sorting has been overidden */
    public void testGeoSearch_sortOnDistanceFieldAscending() throws Exception {
        addToIndex("id", "1", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "2", "lat", "52.3965", "lng", "4.96542", "name", "Other Place");
        assertU(commit());

        SolrQueryRequest req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km threadCount=2}*:*", "sort", "distance asc", "qt", "standard");
        SolrQueryResponse response = h.queryAndResponse("standard", req);
        SolrDocumentList solrDocumentList = retrieveResponseDocuments(response);
        assertEquals(2, solrDocumentList.size());
        assertEquals("1", solrDocumentList.get(0).getFieldValue("id"));
        assertEquals("2", solrDocumentList.get(1).getFieldValue("id"));
    }

    /* Pass condition: Sorting on the field geo_distance should succeed as the parsing of the sorting has been overidden */    
    public void testGeoSearch_sortOnDistanceFieldDescending() throws Exception {
        addToIndex("id", "1", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "2", "lat", "52.3965", "lng", "4.96542", "name", "Other Place");
        assertU(commit());

        SolrQueryRequest req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km threadCount=2}*:*", "sort", "distance desc", "qt", "standard");
        SolrQueryResponse response = h.queryAndResponse("standard", req);
        SolrDocumentList solrDocumentList = retrieveResponseDocuments(response);
        assertEquals(2, solrDocumentList.size());
        assertEquals("2", solrDocumentList.get(0).getFieldValue("id"));
        assertEquals("1", solrDocumentList.get(1).getFieldValue("id"));
    }

    /* Pass condition: Only 1 set of results should be in the response as the GeoDistanceComponent removes the old one */
    public void testGeoSearch_onlyOneSetofResults() throws Exception {
        addToIndex("id", "1", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "2", "lat", "52.3554", "lng", "4.8323", "name", "Slotervaart en Overtoomse Veld");
        addToIndex("id", "3", "lat", "50.8715", "lng", "6.03231", "name", "Kamps Nederland Limburg");
        addToIndex("id", "4", "lat", "50.947", "lng", "5.78302", "name", "Preuve Limburg");
        assertU(commit());

        SolrQueryRequest req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km}*:*", "qt", "standard");
        SolrQueryResponse response = h.queryAndResponse("standard", req);
        
        List results = response.getValues().getAll("response");
        assertEquals(1, results.size());

        SolrDocumentList solrDocumentList = retrieveResponseDocuments(response);
        assertEquals(2, solrDocumentList.size());
        assertEquals("1", solrDocumentList.get(0).getFieldValue("id"));
        assertEquals("2", solrDocumentList.get(1).getFieldValue("id"));
    }

    /* Pass condition: Multiple versions of the same query should still result in the filtering occuring for each. */
    public void testGeoSearch_multipleSearches() throws Exception {
        addToIndex("id", "1", "lat", "52.3629", "lng", "4.89284", "name", "jteam");
        addToIndex("id", "2", "lat", "52.3554", "lng", "4.8323", "name", "Slotervaart en Overtoomse Veld");
        addToIndex("id", "3", "lat", "50.8715", "lng", "6.03231", "name", "Kamps Nederland Limburg");
        addToIndex("id", "4", "lat", "50.947", "lng", "5.78302", "name", "Preuve Limburg");
        assertU(commit());

        SolrQueryRequest req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km}*:*", "qt", "standard");
        SolrQueryResponse response = h.queryAndResponse("standard", req);

        List results = response.getValues().getAll("response");
        assertEquals(1, results.size());

        req = req("q", "{!spatial lat=52.3629 long=4.89284 radius=10 unit=km}*:*", "qt", "standard");
        response = h.queryAndResponse("standard", req);

        results = response.getValues().getAll("response");
        assertEquals(1, results.size());
    }

    // ================================================= Helpers =======================================================

    protected SolrDocumentList retrieveResponseDocuments(SolrQueryResponse response) throws Exception {
        return (SolrDocumentList) response.getValues().get("response");
    }

    protected void addToIndex(SolrInputDocument document) throws IOException {
        SolrQueryRequest request = lrf.makeRequest();
        SolrQueryResponse response = new SolrQueryResponse();
        AddUpdateCommand command = new AddUpdateCommand();
        command.solrDoc = document;
        request.getCore().getUpdateProcessingChain(null).createProcessor(request, response).processAdd(command);
    }

    protected void addToIndex(String... fields) throws IOException {
        SolrInputDocument document = createSolrInputDocument(fields);
        addToIndex(document);
    }

    protected SolrInputDocument createSolrInputDocument(String... fields) {
        if (fields.length % 2 != 0) {
            throw new IllegalArgumentException("Supply both the name and values, field array length must be even");
        }

        SolrInputDocument document = new SolrInputDocument();
        for (int i = 0; i < fields.length; i++) {
            document.addField(fields[i], fields[++i]);
        }

        return document;
    }
}
