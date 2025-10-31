# 自动化主流程脚本
from dp_web import run_with_drissionpage
from at_desktop import main as desktop_main


def main():
    installer_path, email_addr, first_code = run_with_drissionpage()
    desktop_main(installer_path, email_addr, first_code)


if __name__ == "__main__":
    main()
