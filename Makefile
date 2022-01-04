O1 =
O = @
OO = $(O$(V))

GCR = $(OO) echo " GLIB_COMPILE_RESOURCES " $@; glib-compile-resources

org.mnt.ReformDisplay.gresource: org.mnt.ReformDisplay.gresource.xml *.ui
	$(OO) $(GCR) --sourcedir=. org.mnt.ReformDisplay.gresource.xml

GENERATED_FILES = \
	org.mnt.ReformDisplay.gresource

all: $(GENERATED_FILES)

clean:
	$(OO) rm -f $(GENERATED_FILES)
