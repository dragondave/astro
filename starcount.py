from astropy.io import fits
print ("@")
with fits.open("fixtures/axy-small.fits") as axy:
    data = axy[1].data
    print (len(data))  # 1000, hmmmm... = hdul[1].header['NAXIS2'] is also this 1000
with fits.open("fixtures/corr.fits") as corr:
    data = corr[1].data
    print(len(data))
with fits.open("fixtures/rdls.fits") as rdls:
    data = rdls[1].data
    print (len(data))
print ("!")