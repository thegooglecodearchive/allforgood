# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A global list of categories for the SERP in the following format:
"String used in Solr query" : "String displayed in SERP"
"""

CATEGORIES = {  "military families":  "Military Families",
                "(september11 OR (eventrangestart:[0001-01-01T00:00:00Z TO 2011-09-13T23:59:59Z]) AND (eventrangeend:[2011-09-09T00:00:00Z TO *]))":        "September 11",        
                "veterans":           "Veterans",        
                "(education OR tutoring)":          "Education",
                "hunger AND -animal": "Hunger",
                "animals":            "Animals",
                "health":             "Health",
                "seniors":            "Seniors",
                "disaster":           "Disaster Preparation",
                "poverty":            "Poverty"}