/* Copyright 2009 Google Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/


/**
 * Creates a new calendar and attaches it to an element.
 * @param {Element} element the element to attach to.
 * @constructor
 */
vol.Calendar = function(element) {
  this.date_ = new Date();
  this.date_.setDate(1);
  this.events_ = {};
  this.numRows_ = 0;

  // Grab the first <TABLE> inside element.  Assumes that's the calendar table.
  this.table_ = element.getElementsByTagName('table')[0];
  // Grab the first <SELECT> inside element. Assumes that's the period selector.
  this.periodSelector = element.getElementsByTagName('select')[0];
};


vol.Calendar.MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];


vol.Calendar.ROWS = 6;
vol.Calendar.COLUMNS = 7;


/**
 * Display this calendar's next month.
 */
vol.Calendar.prototype.nextMonth = function() {
  this.date_.setMonth(this.date_.getMonth() + 1);
  this.render();
};


/**
 * Display this calendar's previous month.
 */
vol.Calendar.prototype.previousMonth = function() {
  this.date_.setMonth(this.date_.getMonth() - 1);
  this.render();
};


/**
 * Highlights a range of date in the calendar.
 * @param {Date} t0 start date of the the range (inclusive).
 * @param {Date} t1 end date fo the range (inclusive).
 */
vol.Calendar.prototype.markRange = function(t0, t1) {
  if (t0.getTime() > t1.getTime()) {
    var tmp = t0;
    t0 = t1;
    t1 = tmp;
  }
  t0 = vol.Calendar.copyDatePart(t0);
  t1 = vol.Calendar.copyDatePart(t1);
  
  var firstDay = this.getFirstDay();
  if (t0.getTime() < firstDay.getTime()) {
    t0 = firstDay;
  }
  var lastDay = this.getLastDay();
  if (t1.getTime() > lastDay.getTime()) {
    t1 = lastDay;
  }
  for (var d = t0; d.getTime() <= t1.getTime(); d.setDate(d.getDate() + 1)) {
    this.events_[vol.Calendar.dateAsString(d)] = true;
  }
};


/**
 * Remove all highlighted days in the calendar.
 */
vol.Calendar.prototype.clearMarks = function() {
  this.events_ = {};
};


/**
 * Retrieves the currently selected date range.
 * @return {Array.[Date]} an array of two dates representing the start date and
 *     end date of the selected date range.
 */
vol.Calendar.prototype.getDateRange = function() {
  var startDate, endDate;
  switch (this.periodSelector.value) {
    case 'month':
      startDate = vol.Calendar.copyDatePart(this.date_);
      endDate = new Date(startDate.getTime());
      endDate.setMonth(endDate.getMonth() + 1);
      break;
    case 'week':
      startDate = vol.Calendar.copyDatePart(new Date());
      endDate = new Date(startDate.getTime());
      endDate.setDate(endDate.getDate() + 7);
      break;
    case 'weekend':
      startDate = vol.Calendar.copyDatePart(new Date());
      var daysToNextSaturday = 6 - startDate.getDay();
      startDate.setDate(startDate.getDate() + daysToNextSaturday);
      endDate = new Date(startDate.getTime());
      endDate.setDate(endDate.getDate() + 1);
      break;
    case 'today':
      startDate = vol.Calendar.copyDatePart(new Date());
      endDate = startDate;
      break;
  }
  return [startDate, endDate];
};


/**
 * Computes the date of the first day displayed by the calendar.
 * For March 2009 the first day is February the 23rd:
 *  M  T  W  T  F  S  S
 * 23 24 25 26 27 28  1
 * ...
 * @return {Date} the first day displayed by the calendar.
 */
vol.Calendar.prototype.getFirstDay = function() {
  var day = vol.Calendar.copyDatePart(this.date_);
  day.setDate(day.getDate() - (day.getDay() + 6) % 7);
  return day;
};


/**
 * Computes the last day displayed by the calendar.
 * For March 2009 the last day is April the 5h:
 *  M  T  W  T  F  S  S
 * ...
 * 30 31  1  2  3  4  5
 * @return {Date} the last day displayed by the calendar.
 */
vol.Calendar.prototype.getLastDay = function() {
  var day = this.getFirstDay();
  day.setDate(day.getDate() + vol.Calendar.ROWS * vol.Calendar.COLUMNS - 1);
  return day;
};


/**
 * Renders the calendar.
 */
vol.Calendar.prototype.render = function() {
  // sets the title of the calendar
  var month = vol.Calendar.MONTH_NAMES[this.date_.getMonth()]
      + ' ' + this.date_.getFullYear();
  forEachElementOfClass('calendar_month', function(e) {
    e.innerHTML = month;
  }, this.table_);

  // Delete last five rows, if present (that is, after changing the
  // current month).
  var numRows = this.table_.rows.length;
  if (numRows >= 6) {
    for (var i = 0; i < 6; i++) {
      this.table_.deleteRow(this.table_.rows.length - 1);
    }
  }

  var tbody = this.table_.getElementsByTagName('tbody')[0];
  for (var row = 0, day = this.getFirstDay(); row < vol.Calendar.ROWS; row++) {
    var tr = document.createElement('tr');
    tbody.appendChild(tr);
    for (var col = 0; col < vol.Calendar.COLUMNS; col++) {
      var classes = [];
      // days cannot be marked as 'event' and 'weekend' at the same time
      // to avoid multi-class problems with IE.
      if (vol.Calendar.dateAsString(day) in this.events_) {
        classes.push('calendar_days_event');
      } else if ((day.getDay() + 6) % 7 > 4) {
        classes.push('calendar_days_weekend');
      }
      if (vol.Calendar.isToday(day)) {
        classes.push('calendar_days_today');
      }
      var td = document.createElement('td');
      if (classes.length > 0) {
        td.className = classes.join(' ');
      }
      tr.appendChild(td);
      td.innerHTML = day.getDate();
      day.setDate(day.getDate() + 1);
    }
  }

  this.table_.style.display = '';
};


/**
 * Checks whether the given date is today (ignoring hours, minutes and seconds).
 * @param {Date} date a date.
 * @return {boolean} whether the given date is today.
 */
vol.Calendar.isToday = function(date) {
  var today = new Date();
  return date.getFullYear() == today.getFullYear()
      && date.getMonth() == today.getMonth()
      && date.getDate() == today.getDate();
};


/**
 * Copies the date part of a date.
 * @param {Date} date a date.
 * @return {Date} a new date whose year, month and day field are copied from the
 *     the argument.
 */
vol.Calendar.copyDatePart = function(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
};


/**
 * Converts a date to a 'yyyy-mm-dd' formatted string.
 * @param {Date} date a date.
 * @return {string} the date formatted as per 'yyyy-mm-dd'.
 */
vol.Calendar.dateAsString = function(date) {
  var buffer = [date.getFullYear(), '-'];
  var month = date.getMonth() + 1; // Date.getMonth() returns 0 based months
  if (month < 10) {
    buffer.push('0');
  }
  buffer.push(month, '-');
  var day = date.getDate();
  if (day < 10) {
    buffer.push('0');
  }
  buffer.push(day);
  return buffer.join('');
};


/**
 * Converts a 'yyyy-mm-dd' formatted string to a date.
 * @param {string} str the string to convert.
 * @return {Date|null} the date, or null if the string cannot be converted.
 */
vol.Calendar.dateFromString = function(str) {
  var matches = /^(\d{4})-(\d{2})-(\d{2})$/.exec(str);
  return !matches ? null : new Date(
      Number(matches[1]),
      Number(matches[2]) - 1, // month is 0 based.
      Number(matches[3]));
};
