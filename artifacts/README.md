# Prototype illustrations and historical diagrams

- `smart-street-prototype.png`: generated visual layout of the ESP32, three LEDs, PIR, buzzer and Logitech camera. The GPIO25/GPIO33 LED labels describe the proposed independent wiring. Current firmware controls the GPIO26 lamp only; this illustration is not a hole-by-hole electrical wiring guide.
- `smart-street-prototype-prompt.txt`: the image-generation prompt.
- `esp32-complete-connections.*`, `esp32-mb102-all-connections.*` and their drawing scripts: historical diagrams from the earlier GPIO2/GPIO5 wiring. They do not match the current firmware pins.
- `pir-motion-control.png`: historical dashboard capture from the earlier chirp behavior; current PIR motion response is silent.

For current GPIO26 LED, GPIO4 buzzer, GPIO27 PIR, resistor and ground connections, follow [the firmware wiring guide](../firmware/esp32_street_light/README.md).
