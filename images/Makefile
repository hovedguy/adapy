pull:
	docker pull krande/ada:base

build:
	docker krande/ada:base cp tests/test_code_aster_fem.py krande/ada:/

test:
	docker container cp tests/test_code_aster_fem.py krande/ada:/ && docker exec -it krande/ada:base bash -c "pytest"