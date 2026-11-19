# A scratch copy takes a submodule's listed files, and leaves an untracked nested repo out

A scratch copy must hold a submodule's code, since tests read it. Copying each submodule's
directory whole was considered instead of listing its files with git. It is not used, because the
copy would then carry the submodule's ignored files -- caches and build output -- which the copy of
the repo itself leaves out. A repo nested in the working tree that is not a submodule is left out
too: git does not treat it as part of the repo, so copying it could pull in anything that happens
to sit there. Reopen this if a project's tests need the ignored files of a submodule, or the code
of a nested repo that is not a submodule.
