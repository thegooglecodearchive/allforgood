package nl.jteam.search.solrext.spatial.lucene.util;

/**
 * Enum representing difference distance units, currently only kilometers and miles
 */
public enum DistanceUnit {

    MILES("miles"),
    KILOMETERS("km");

    private static final double MILES_KILOMETRES_RATIO = 1.609344;
    
    private String unit;

    /**
     * Creates a new DistanceUnit that represents the given unit
     *
     * @param unit Distance unit in String form
     */
    DistanceUnit(String unit) {
        this.unit = unit;
    }

    /**
     * Returns the DistanceUnit which represents the given unit
     *
     * @param unit Unit whose DistanceUnit should be found
     * @return DistanceUnit representing the unit
     * @throws IllegalArgumentException if no DistanceUnit which represents the given unit is found
     */
    public static DistanceUnit findDistanceUnit(String unit) {
        if (MILES.getUnit().equals(unit)) {
            return MILES;
        }

        if (KILOMETERS.getUnit().equals(unit)) {
            return KILOMETERS;
        }

        throw new IllegalArgumentException("Unknown distance unit " + unit);
    }

    /**
     * Converts the given distance from the given DistanceUnit, to the given DistanceUnit
     *
     * @param distance Distance to convert
     * @param from Unit to convert the distance from
     * @param to Unit of distance to convert to
     * @return Given distance converted to the distance in the given uni
     */
    public static double convert(double distance, DistanceUnit from, DistanceUnit to) {
        if (from == to) {
            return distance;
        }
        return (to == MILES) ? distance / MILES_KILOMETRES_RATIO : distance * MILES_KILOMETRES_RATIO;
    }

    // =============================================== Getters / Setters ===============================================
    
    /**
     * Returns the string representation of the distance unit
     *
     * @return String representation of the distance unit
     */
    public String getUnit() {
        return unit;
    }
}

