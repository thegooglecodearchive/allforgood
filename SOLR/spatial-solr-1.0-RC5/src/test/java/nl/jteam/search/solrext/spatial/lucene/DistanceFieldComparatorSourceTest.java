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

package nl.jteam.search.solrext.spatial.lucene;

import org.junit.Test;
import org.junit.Before;
import static org.easymock.EasyMock.*;
import static org.junit.Assert.*;
import org.apache.lucene.search.FieldComparator;
import nl.jteam.search.solrext.spatial.lucene.distance.DistanceFilter;
import nl.jteam.search.solrext.spatial.lucene.DistanceFieldComparatorSource;

/**
 * @author Martijn van Groningen
 * @since Sep 28, 2009
 */
public class DistanceFieldComparatorSourceTest {

    private DistanceFilter mockDistanceFilter;
    private DistanceFieldComparatorSource comparatorSource;

    @Before
    public void setUp() {
        mockDistanceFilter = createMock(DistanceFilter.class);
        comparatorSource = new DistanceFieldComparatorSource(mockDistanceFilter);
    }

    @Test
    public void testNewComparator_lessThan() throws Exception {
        expect(mockDistanceFilter.getDistance(1)).andReturn(0.1);
        expect(mockDistanceFilter.getDistance(2)).andReturn(0.2);
        replay(mockDistanceFilter);

        FieldComparator fieldComparator = comparatorSource.newComparator("field", 3, 0, false);
        fieldComparator.copy(0, 1);
        fieldComparator.copy(1, 2);
        assertEquals(-1, fieldComparator.compare(0, 1));

        verify(mockDistanceFilter);
    }

    @Test
    public void testNewComparator_greaterThan() throws Exception {
        expect(mockDistanceFilter.getDistance(1)).andReturn(0.2);
        expect(mockDistanceFilter.getDistance(2)).andReturn(0.1);
        replay(mockDistanceFilter);

        FieldComparator fieldComparator = comparatorSource.newComparator("field", 3, 0, false);
        fieldComparator.copy(0, 1);
        fieldComparator.copy(1, 2);
        assertEquals(1, fieldComparator.compare(0, 1));

        verify(mockDistanceFilter);
    }

    @Test
    public void testNewComparator_equal() throws Exception {
        expect(mockDistanceFilter.getDistance(1)).andReturn(0.2);
        expect(mockDistanceFilter.getDistance(2)).andReturn(0.2);
        replay(mockDistanceFilter);

        FieldComparator fieldComparator = comparatorSource.newComparator("field", 3, 0, false);
        fieldComparator.copy(0, 1);
        fieldComparator.copy(1, 2);
        assertEquals(0, fieldComparator.compare(0, 1));

        verify(mockDistanceFilter);
    }

}
