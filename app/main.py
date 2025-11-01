# 自动化主流程脚本
import os
import sys
from dp_web import run_with_drissionpage
from at_desktop import main as desktop_main
from logger import get_logger

logger = get_logger("MAIN")


def main():
    try:
        logger.running("开始执行自动化流程")
        installer_path, email_addr, first_code = run_with_drissionpage()
        desktop_main(installer_path, email_addr, first_code)
        logger.success("全流程执行成功")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"任务执行失败: {error_msg}")
        logger.failed(f"任务执行失败: {error_msg}", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
