package nl.jteam.search.solrext.spatial.lucene.geometry;

import java.text.DecimalFormat;

/**
 * @author Chris Male
 */
public class FastTrigExample {

    private static double B = 4 / Math.PI;
    private static double C = -4 / (Math.PI * Math.PI);
    private static double P = 0.218;

    static double sine(double x) {
        double y = B * x + C * x * Math.abs(x);
        y = P * (y * Math.abs(y) - y) + y;   // Q * y + P * y * abs(y)
        return y;
    }

//    @Test
    public void testQuickierSin() {
      DecimalFormat format = new DecimalFormat("0.########");
        for (int i = 0; i < 180; i++) {
            double x = 0.01745329251994 * i;
            double delta = Math.sin(x) - sine(x);
//            System.out.println(i + " => " + format.format(delta));
        }
    }

    public void testSinSpeed() {
        long start = System.currentTimeMillis();
        for (int z = 0; z < 100000; z++) {
            for (int i = 0; i < 360; i++) {
                double x = 0.01745329251994 * i;
                double result = sine(x);
            }
        }
        long end = System.currentTimeMillis();
        //System.out.println(end - start);
    }
}
