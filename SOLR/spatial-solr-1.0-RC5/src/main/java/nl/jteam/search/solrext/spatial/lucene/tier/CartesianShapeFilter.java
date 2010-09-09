package nl.jteam.search.solrext.spatial.lucene.tier;

import java.io.IOException;
import java.util.List;
import java.util.BitSet;

import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.Term;
import org.apache.lucene.index.TermDocs;
import org.apache.lucene.search.Filter;
import org.apache.lucene.search.DocIdSet;
import org.apache.lucene.util.NumericUtils;
import org.apache.lucene.util.DocIdBitSet;

/**
 * CartesianShapeFilter is a proper Lucene filter that filters out documents that are not within the boxes that define
 * a certain CartesianShape overlaps.  For example, if a shape overlaps boxes 1, 3 and 6, then a document that has been
 * plotted to be within box 5 will be filtered out.
 */
public class CartesianShapeFilter extends Filter {

    private CartesianShape cartesianShape;
    private String fieldName;

    /**
     * Creates a new CartesianShapeFilter that will filter out documents that are not within the boxes defined in the
     * given CartesianShape.  The Filter will check the values of the given field to see whether a document is within a
     * certain box.
     *
     * @param cartesianShape CartesianShape containing boxes that documents must be within, in order not to be filtered out
     * @param fieldName Name of the field in the documents that will be checked for what boxes the document is in
     */
    public CartesianShapeFilter(CartesianShape cartesianShape, String fieldName) {
        this.cartesianShape = cartesianShape;
        this.fieldName = fieldName;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public DocIdSet getDocIdSet(IndexReader reader) throws IOException {
        BitSet bits = new BitSet(reader.maxDoc());

        TermDocs termDocs = reader.termDocs();
        List<Double> area = cartesianShape.getBoxIds();
        for (double boxId : area) {
            termDocs.seek(new Term(fieldName, NumericUtils.doubleToPrefixCoded(boxId)));

            // iterate through all documents which have this boxId
            while (termDocs.next()) {
                bits.set(termDocs.doc());
            }
        }
        return new DocIdBitSet(bits);
    }
}
