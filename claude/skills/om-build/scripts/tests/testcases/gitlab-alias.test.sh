:setup-glab
tests:ensure env -u OM_GUI -u OM_MONO bash "$TEST_GLAB_FIXTURE" --gate
tests:assert-stdout "GUI=$HOME/Documents/GitLab/openmarket-chat-gitlab"
tests:assert-stdout "MONO=$HOME/Documents/GitLab/openmarket-internal"
tests:assert-stdout 'arg=--gate'

ln -s "$TEST_GLAB_FIXTURE" "$(tests:get-tmp-dir)/om-glab"
tests:ensure env OM_GUI='/a GUI with spaces' OM_MONO='/a core with spaces' \
	bash "$(tests:get-tmp-dir)/om-glab" --force --no-gui
tests:assert-stdout 'GUI=/a GUI with spaces'
tests:assert-stdout 'MONO=/a core with spaces'
tests:assert-stdout 'arg=--force'
tests:assert-stdout 'arg=--no-gui'

tests:eval env TEST_HOSTED_EXIT=17 bash "$TEST_GLAB_FIXTURE" --gate
tests:assert-exitcode 17
