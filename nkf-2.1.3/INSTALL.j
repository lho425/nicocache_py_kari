INSTALL$B$N;EJ}(B

	    Sun Sep  8 14:11:16 JST 2002

Makefile $B$,$"$k$N$G!"(B
    CC
    CFLAGS
    PERL
$B$,@5$7$$$+$I$&$+$r3NG'$7$F!"(B
    make
$B$7$F$/$@$5$$!#(BLinux, Solaris, Mac OS X $B$GF0:n3NG'$7$F$$$^$9!#(B

mkstemp $B$,$J$$>l9g$O!"(Bconfig.h $B$N(B #define OVERWRITE $B$r%3%a%s%H%"%&%H(B
$B$7$F$/$@$5$$!#(B

Perl $B%b%8%e!<%k$r:n$k$K$O!"(B
    make perl
$B$G$9!#(BNKF.mod $B2<$K$G$-$^$9!#$=$A$i$G!"(Bperl Makefile.PL; make
$B$G$b(BOk$B!#(B Perl 5 $B0J>e$GF0:n$7$^$9!#(B5.6, 5.8 $B$GF0:n3NG'$7$F$$$^$9!#(B

make test $B$G%F%9%H$,9T$o$l$^$9!#(BNKF.mod $B$G$b(B make test
$B$,2DG=!#(B

