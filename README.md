# Factory I/O 스마트 팩토리 자동화

Factory I/O 가상 공장에서 파란색과 초록색 물체를 가공하고 분류하는 프로젝트입니다.

Python 프로그램이 공장의 제어 역할을 합니다. 센서로 물체 상태를 확인하고, 컨베이어·가공기·푸셔에 신호를 보내 공정이 진행되도록 만들었습니다.

## 시연 영상

<video src="파이널 프로젝트.mp4" controls playsinline muted loop width="100%"></video>

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
| `pyfa-project.py` | 공장을 제어하는 Python 실행 프로그램 |
| `요구사항 명세서.md` | 프로젝트 기능과 동작 조건을 정리한 문서 |
| `스마트팩토리 자동화 프로젝트 보고서.md` | 구현 내용과 결과를 정리한 문서 |

## 준비 사항

- Factory I/O
- Python 3
- `pymodbus` 라이브러리

프로젝트 폴더의 터미널에서 아래 명령을 실행합니다.

```bash
python -m pip install -r requirements.txt
```

## 실행 방법

1. Factory I/O에서 `Modbus_project.factoryio` 파일을 엽니다.
2. Driver를 **Modbus TCP/IP Server**로 설정합니다.
3. Factory I/O를 **RUN** 상태로 전환합니다.
4. 프로젝트 폴더에서 터미널을 엽니다.
5. `pyfa-project.py`의 IP 주소, 포트 번호, Unit ID가 Factory I/O 설정과 같은지 확인합니다.
6. 아래 명령으로 제어 프로그램을 실행합니다.


```bash
python pyfa-project.py
```

프로그램은 Factory I/O 연결을 확인한 뒤 `auto_start_factory_io(reset_outputs=True)`를 실행하여 자동 운전을 시작합니다.

기본 통신 설정은 다음과 같습니다.

```python
IP_ADDRESS = '210.119.14.76'
PORT = 502
UNIT_ID = 1
```

## 정상 동작 확인

- Factory I/O가 RUN 상태인지 확인합니다.
- Driver가 **Modbus TCP/IP Server**로 연결되어 있는지 확인합니다.
- 터미널에 `Factory I/O Modbus connected`와 `Factory I/O automatic process started`가 출력되는지 확인합니다.
- 파란색 물체가 비전 센서를 지난 뒤 푸셔로 밀려 분류되는지 확인합니다.
- 초록색 물체가 푸셔에 밀리지 않고 다음 공정으로 이동하는지 확인합니다.

## 공정 정지

공정을 멈추려면 프로그램을 실행한 터미널에서 `Ctrl+C`를 누릅니다.

프로그램은 `stop_all()`을 호출하여 컨베이어, 푸셔, 가공기 등의 제어 출력을 정지하고 연결을 닫습니다.

## 문제 발생 시 확인할 항목

- Factory I/O가 실행 중이며 RUN 상태인지 확인합니다.
- Driver가 **Modbus TCP/IP Server**로 설정되어 있는지 확인합니다.
- IP 주소, Port, Unit ID가 `pyfa-project.py` 설정과 같은지 확인합니다.
- 방화벽이 Port `502` 통신을 막고 있지 않은지 확인합니다.
- Factory I/O의 I/O 주소와 `pyfa-project.py`의 I/O 매핑이 같은지 확인합니다.
- Driver 설정을 변경했다면 실행 중인 프로그램을 종료한 뒤 다시 실행합니다.
