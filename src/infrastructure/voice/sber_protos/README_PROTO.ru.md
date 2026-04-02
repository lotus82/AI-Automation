# SaluteSpeech gRPC: proto и генерация Python

## TODO (обязательно к прочтению)

1. **Распознавание (STT)** в проекте собрано из контракта **`smartspeech.recognition.v2`** — файлы **`recognition.proto`** и эталон **`recognition-2705-2ae60b27890aa4473ebe324ca4132223.proto`** (должны совпадать).  
   Ответы: `RecognitionResponse` с `oneof response` (`transcription` | `backend_info` | `insight` | `vad`); текст и `eou` — внутри **`Transcription`**.

2. **Синтез (TTS)** по-прежнему из `synthesis/v1/synthesis.proto` (репозиторий [salute-developers/salute-speech](https://github.com/salute-developers/salute-speech)) + `task.proto` для асинхронных RPC в том же пакете.

3. **Документация** Сбера по потоковому gRPC:  
   [Потоковое распознавание gRPC](https://developers.sber.ru/docs/ru/salutespeech/api/grpc/recognition-stream-2)  
   и [proto recognition-2705](https://developers.sber.ru/files/salutespeech/recognition-2705.proto) (актуальная схема может совпадать с v2 в каталоге).

4. Потоковый RPC — **`Recognize`** (bidirectional stream). Это не путать с файловым асинхронным REST/gRPC-задачами в других разделах API.

5. **Пересборка** после обновления `.proto` из документации (из корня репозитория проекта):

   ```bash
   pip install "grpcio-tools>=1.71,<2"
   cd src/infrastructure/voice/sber_protos
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. \
     google/protobuf/duration.proto google/protobuf/timestamp.proto \
     task.proto recognition.proto synthesis.proto
   ```

   Затем в сгенерированных `*_pb2.py` и `*_pb2_grpc.py` замените строки вида `import task_pb2` на **`from . import task_pb2`** (и аналогично для `recognition_pb2` / `synthesis_pb2`), чтобы пакет импортировался как `src.infrastructure.voice.sber_protos`.

6. Файлы **`google/protobuf/duration.proto`** и **`timestamp.proto`** здесь — укороченные вендорные копии well-known типов для автономной компиляции; при расхождении с вашей версией `protobuf` сверяйтесь с [protocolbuffers/protobuf](https://github.com/protocolbuffers/protobuf).

7. Имена сгенерированных модулей — `recognition_pb2`, `synthesis_pb2` (не единый `smartspeech_pb2.py`); приложение импортирует их из этого каталога.
