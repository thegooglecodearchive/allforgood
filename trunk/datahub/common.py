#!/usr/bin/python
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

"""provider specifics"""

import providers

UI_COMMON_DIR = "/home/footprint/public_html/"

def main():
  
  js = """
/**** Note:
      this is an automatically generated file and
      any manual changes will be overwritten the
      next time the pipeline runs
"****/\n\n"""
  
  js += providers.updateProviderNamesScript()

  fname = UI_COMMON_DIR + "pipeline_common.js"
  fh = open(fname, "w")
  fh.write(js)
  fh.close()


if __name__ == "__main__":
  main()
