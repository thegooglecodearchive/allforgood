from csv import DictReader, DictWriter, excel_tab, register_dialect, QUOTE_NONE
import sys
class our_dialect(excel_tab):
  quotechar = ''
  quoting = QUOTE_NONE
register_dialect('our-dialect', our_dialect)

def retransform(fname):
  print fname
  f = open(fname, "r")
  csv_reader = DictReader(f, dialect='our-dialect')
  csv_reader.next()
  fnames = csv_reader.fieldnames[:]
  fnames.append("c:eventrangeend:datetime")
  fnames.append("c:eventrangestart:datetime")
  fnamesdict = dict([(x, x) for x in fnames])
  f = open(fname, "r")
  csv_reader = DictReader(f, dialect='our-dialect')
  csv_writer = DictWriter(open (fname + '.transformed', 'w'), dialect='excel-tab', fieldnames=fnames)
  csv_writer.writerow(fnamesdict)
  for rows in csv_reader:
    for key in rows.keys():
      if key.find(':dateTime') != -1:
        rows[key] += 'Z'
      elif key.find(':integer') != -1:
        if rows[key] == '':
          rows[key] = 0
        else:
          rows[key] = int(rows[key])
      
    # Split the date range into separate fields
    # event_date_range can be either start_date or start_date/end_date
    split_date_range = rows["event_date_range"].split('/')
    rows["c:eventrangeend:datetime"] = split_date_range[0]
    if len(split_date_range) > 1:
      rows["c:eventrangestart:datetime"] = split_date_range[1]
    
    # Fix the +1000 to lat/long hack
    rows['c:latitude:float'] = float(rows['c:latitude:float']) - 1000.0
    rows['c:longitude:float'] = float(rows['c:longitude:float']) - 1000.0
    csv_writer.writerow(rows)
  
def main(argv):
  for arg in sys.argv[1:]:
    retransform(arg)
if __name__ == "__main__":
    main(sys.argv[1:])

