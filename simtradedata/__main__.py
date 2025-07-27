#!/usr/bin/env python3
"""
SimTradeData 模块入口点

允许通过 `python -m simtradedata` 调用命令行工具。
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
