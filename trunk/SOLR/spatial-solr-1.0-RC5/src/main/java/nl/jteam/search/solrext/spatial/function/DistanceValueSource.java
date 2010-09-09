package nl.jteam.search.solrext.spatial.function;

import org.apache.solr.search.function.ValueSource;
import org.apache.solr.search.function.DocValues;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.document.Fieldable;
import nl.jteam.search.solrext.spatial.FieldValueSource;

import java.util.Map;
import java.io.IOException;

public class DistanceValueSource extends ValueSource {
  private String field;
  private FieldValueSource fvs;

  public DistanceValueSource(String field, FieldValueSource fvs) {
    this.field = field;
    this.fvs = fvs;
  }

  @Override public DocValues getValues(Map map, IndexReader indexReader) throws IOException {
    return new DocValues() {
      public float floatVal(int doc) {
        return (float) doubleVal(doc);
      }

      public int intVal(int doc) {
        return (int) doubleVal(doc);
      }

      public long longVal(int doc) {
        return (long) doubleVal(doc);
      }

      public double doubleVal(int doc) {
        Fieldable[] values = fvs.getValues(doc);
        if (values != null) {
          double distance = Double.parseDouble(values[0].stringValue());
          return distance;
        }
        return 0D;
      }

      public String strVal(int doc) {
        return Double.toString(doubleVal(doc));
      }

      public String toString(int doc) {
        return description() + " " + doubleVal(doc);
      }
    };
  }

  public boolean equals(Object o) {
    return o.getClass() == DistanceValueSource.class && this.field.equals(((DistanceValueSource) o).field);
  }

  public int hashCode() {
    return DistanceValueSource.class.hashCode() + field.hashCode();
  }

  public String description() {
    return "dist(" + field + ")";
  }
}
