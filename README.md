# Factory I/O 스마트 팩토리 자동화

Factory I/O 가상 공장에서 파란색과 초록색 물체를 가공하고 분류하는 프로젝트입니다.

Python 프로그램이 공장의 제어 역할을 합니다. 센서로 물체 상태를 확인하고, 컨베이어·가공기·푸셔에 신호를 보내 공정이 진행되도록 만들었습니다.

## 동작 과정

1. `MC0`과 `MC1` 가공기가 동시에 작업을 시작합니다.
2. 파란색 물체는 `MC0`, 초록색 물체는 `MC1` 가공기로 들어갑니다.
3. 가공이 끝난 물체는 컨베이어를 따라 분류 구역으로 이동합니다.
4. 비전 센서가 물체의 색상 정보를 확인합니다.
5. 파란색 물체가 감지되면 Python 프로그램이 푸셔에 신호를 보냅니다.
6. 푸셔는 파란색 물체만 옆으로 밀어 분류합니다.
7. 초록색 물체는 푸셔가 동작하지 않은 상태로 다음 위치까지 이동합니다.

푸셔가 색을 직접 판단하는 것은 아닙니다. 비전 센서가 물체 정보를 읽고, Python 프로그램이 그 정보를 바탕으로 푸셔를 움직입니다.

## 프로젝트 파일

| 파일 | 설명 |
| --- | --- |
| `Modbus_project.factoryio` | Factory I/O에서 실행하는 가상 공장 장면 |
| `pyfa-project.ipynb` | 공장을 제어하는 Python Jupyter Notebook |
| `요구사항 명세서.md` | 프로젝트 기능과 동작 조건을 정리한 문서 |
| `프로젝트 결과 보고서.md` | 구현 내용과 결과를 정리한 문서 |

## 준비 사항

- Factory I/O
- Python 3
- Jupyter Notebook 또는 VS Code의 Jupyter 확장
- `pymodbus` 라이브러리

`pymodbus`가 설치되어 있지 않다면 터미널에서 아래 명령을 실행합니다.

```bash
pip install pymodbus
```

## 실행 방법

1. Factory I/O에서 `Modbus_project.factoryio` 파일을 엽니다.
2. Driver를 **Modbus TCP/IP Server**로 설정합니다.
3. Factory I/O를 **RUN** 상태로 전환합니다.
4. `pyfa-project.ipynb` 파일을 엽니다.
5. 첫 번째 셀의 IP 주소, 포트 번호, Unit ID가 Factory I/O 설정과 같은지 확인합니다.
6. 노트북 셀을 위에서 아래 순서대로 실행합니다.
7. `auto_start_factory_io()`가 포함된 자동 운전 시작 셀을 실행합니다.

기본 통신 설정은 다음과 같습니다.

```python
IP_ADDRESS = '210.119.14.76'
PORT = 502
UNIT_ID = 1
```

## 정상 동작 확인

- Factory I/O가 RUN 상태인지 확인합니다.
- Driver가 **Modbus TCP/IP Server**로 연결되어 있는지 확인합니다.
- 노트북에 `connected = True`가 출력되는지 확인합니다.
- 파란색 물체가 비전 센서를 지난 뒤 푸셔로 밀려 분류되는지 확인합니다.
- 초록색 물체가 푸셔에 밀리지 않고 다음 공정으로 이동하는지 확인합니다.

## 공정 정지

공정을 멈추려면 노트북에서 아래 코드를 실행합니다.

```python
stop_all()
```

실행하면 컨베이어, 푸셔, 가공기 등의 제어 출력이 정지합니다.

## 문제 발생 시 확인할 항목

- Factory I/O가 실행 중이며 RUN 상태인지 확인합니다.
- Driver가 **Modbus TCP/IP Server**로 설정되어 있는지 확인합니다.
- IP 주소, Port, Unit ID가 노트북 설정과 같은지 확인합니다.
- 방화벽이 Port `502` 통신을 막고 있지 않은지 확인합니다.
- Factory I/O의 I/O 주소와 노트북의 I/O 매핑이 같은지 확인합니다.
- Driver 설정을 변경했다면 노트북 커널을 다시 시작한 뒤 재연결합니다.