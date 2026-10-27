# Render Redistort

트래킹 카메라로 렌더한 이미지와 디스토션 STMap을 받아, 촬영본의 왜곡 공간에 맞춘 합성용 소스를 저장하는 Codex 스킬입니다.

## 채팅창 한 줄로 설치

Codex 채팅창에 아래 문장을 그대로 입력하세요. 터미널 명령을 직접 실행할 필요가 없습니다.

```text
https://github.com/luffy415/render-redistort 저장소의 skills/render-redistort 스킬을 설치하고 필요한 실행 환경 준비와 자체 검증까지 완료해줘.
```

Codex가 스킬 등록 → 전용 Python 환경 준비 → 테스트를 진행합니다. 로컬 환경에서 필요한 실행/네트워크 권한은 적용됩니다. 등록을 마친 다음 대화부터 `$render-redistort`로 사용할 수 있습니다. 외부 API 키나 GPU는 필요 없습니다.

## 사용

렌더 시퀀스, 디스토션 맵, 렌더/렌즈 설정 파일을 함께 제공하고 요청하세요.

```text
$render-redistort 첨부한 렌더에 이 디스토션 맵을 적용해 최종 합성용 소스로 저장해줘. 원본 포맷과 비트 깊이를 유지하고, 추가 손실 압축 없이 저장해줘.
```

기본 지원: RGB/RGBA EXR(HALF/FLOAT), PNG8/16, TIFF. 정적/프레임별 STMap, 픽셀 좌표 NPY 맵, 선형 RGB와 sRGB, straight/premultiplied alpha를 명시적으로 처리합니다. 원본을 덮어쓰지 않고 새 폴더에 같은 파일명/확장자로 저장하며, 저장 후 다시 읽어 픽셀·비트 깊이·색 메타데이터·프레임 대응을 검사합니다.

**왜곡 변환에는 재샘플링이 필요하므로 픽셀 값까지 수학적으로 무손실인 작업은 아닙니다.** 이 스킬은 불필요한 축소, 비트 깊이 감소, 추가 손실 압축, 알파/색공간의 임의 변경을 피합니다. HDR/음수 float 값은 유지하고 native 정수 양자화와 클리핑은 기록합니다.

MOV/MP4/JPEG, Log/DPX, deep/multipart/multilayer EXR에는 별도 검증 경로가 필요합니다. 손실 코덱을 다시 인코딩하면서 “원래 포맷이고 화질 손실도 없다”고 보장하지 않습니다. 지원하지 않는 소스는 임의 변환하지 않고 필요한 조건이나 무손실 대안을 설명합니다.

## 결과물

- 입력과 같은 포맷·비트 깊이의 합성용 이미지 시퀀스
- 입력 프레임 번호와 이름 유지, 별도 리타이밍 없음
- 입력/출력 해시, 색/알파 처리, 맵 커버리지, 저장 검증이 담긴 manifest
- 필요하면 별도로 생성한 확인용 미리보기

맵의 출력 크기가 최종 촬영본 해상도입니다. 예를 들어4224×2376 overscan 렌더를 전용 맵으로3840×2160에 대응시키며, 별도 축소나 임의 크롭을 추가하지 않습니다. 인물 키/로토와 최종 색보정은 별도 작업입니다.

## 구성과 검증

[스킬 지침](skills/render-redistort/SKILL.md) · [작업 JSON](skills/render-redistort/references/job-schema.md) · [포맷/품질 범위](skills/render-redistort/references/formats-and-quality.md) · [설치 상세](skills/render-redistort/references/setup.md)

Python3.11–3.13. 검증 환경: Windows/Python3.13. 설치 시 자체 합성 데이터로 포맷 정밀도, HDR, 알파 테두리, UV 방향, 프레임별 맵, 덮어쓰기/빈 프레임/커버리지 거부를 확인합니다. 실제 촬영 소스는 테스트나 저장소에 포함하지 않습니다.

개발자용 로컬 설치: `python install.py`. 직접 검사: `python skills/render-redistort/scripts/self_test.py` (requirements 설치 후).

License: MIT. NumPy/SciPy/OpenImageIO는 전용 환경에 설치되며 각각의 라이선스를 따릅니다.
