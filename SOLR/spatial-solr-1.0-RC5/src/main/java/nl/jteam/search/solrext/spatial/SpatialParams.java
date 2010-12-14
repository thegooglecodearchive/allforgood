package nl.jteam.search.solrext.spatial;

/**
 * Spatial Query Parameters
 */
public interface SpatialParams {
    String LAT = "lat";
    String LNG = "long";
    String RADIUS = "radius";
    String UNIT = "unit";
    String CALC = "calc";

    String LAT_FIELD_KEY = "latField";
    String LNG_FIELD_KEY = "lngField";
    String DISTANCE_FIELD_KEY = "distanceField";
    String TIER_FIELD_KEY = "tierPrefix";
    String THREAD_COUNT_KEY = "threadCount";

    String LAT_FIELD_DEFAULT = "lat";
    String LNG_FIELD_DEFAULT = "lng";
    String DISTANCE_FIELD_DEFAULT = "geo_distance";
    String TIER_FIELD_DEFAULT = "_tier_";

    String ARC_CALC_PARAM = "arc";
    String PLANE_CALC_PARAM = "plane";
}
