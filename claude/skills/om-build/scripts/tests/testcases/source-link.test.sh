:setup-gate
mkdir -p "$OM_GUI/node_modules/registry-copy"
ln -s ../registry-copy "$OM_GUI/node_modules/@openmarket/rooms-client"
tests:ensure bash "$TEST_HOSTED_SCRIPT" --gate
tests:assert-stdout 'NOT LINKED (registry copy)'
tests:assert-stdout 'rooms-client is not linked to the monorepo source'

rm "$OM_GUI/node_modules/@openmarket/rooms-client"
ln -s "$OM_MONO/packages/rooms-client" "$OM_GUI/node_modules/@openmarket/rooms-client"
tests:ensure bash "$TEST_HOSTED_SCRIPT" --gate
tests:assert-stdout "linked -> $(realpath "$OM_MONO/packages/rooms-client")"

rm "$OM_GUI/node_modules/@openmarket/rooms-client"
tests:ensure bash "$TEST_HOSTED_SCRIPT" --gate
tests:assert-stdout 'NOT LINKED (registry copy)'
