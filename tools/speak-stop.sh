#!/bin/bash
# Alt+S — stop reading
kill $(pgrep -f spd-say) 2>/dev/null
