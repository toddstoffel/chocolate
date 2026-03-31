@echo off
:: -----------------------------------------------------------------------------
:: Here I am setting up my Companies cerfticate athority 

mkdir certs db private

:: here we create a dummy index file - this creates a size 0 file
type NUL > db/index

:: this places randon number into the 'db/serial' file
openssl rand -hex 16 > db/serial

:: inits a sequencial number file
echo 1001 > db/crlnumber

echo create root CA cert request and private key
echo CA name is set in rootca.conf under [ca_dn] commonName
echo We used passphrase: FairComQA
openssl req -new -out rootca.csr -keyout ./private/rootca.key -config rootca.conf

echo create root CA cert
openssl ca -selfsign -config rootca.conf -in rootca.csr -out rootca.pem -extensions ca_ext

:: now we have our root certificate. This is our certificate authority used to sign all other certs.
:: -----------------------------------------------------------------------------

:: -----------------------------------------------------------------------------
echo creating server (ctree_ssl.pem) certificate
:: create server private key
set name=ctree_ssl
openssl genrsa -out %name%.key 2048 

:: create certificate signing request
openssl req -new -sha256 -key %name%.key -config rootca.conf -out %name%.csr -subj "/C=US/ST=Missouri/L=Columbia/O=FairCom Corporation/OU=Security Department/CN=localhost/emailAddress=support@faircom.com" -extensions server_ext

:: sign certificate with rootca key
:: Modify rootca.conf [server_ext] subjectAltName for web browser access to this server
openssl ca -md sha256 -days 3650 -in %name%.csr -out %name%.pem -keyfile private/rootca.key -config rootca.conf -cert rootca.pem -extensions server_ext

:: append the signing CA cert.
type rootca.pem >> %name%.pem

echo creating public copy of server certificate (ctsrvr.pem)
:: create copy of server cert for client usage. 
copy %name%.pem ctsrvr.pem

:: combine server key into server cert.
type %name%.key >>%name%.pem

:: The difference betwwen the server's .pem (ctree_ssl.pem) and the client .pem
:: (ctsrvr.pem) is that the client does not have the server's private key.
:: But the server's .pem (faircom.pem) has the server's private key appended to the end.
:: -----------------------------------------------------------------------------

:: -----------------------------------------------------------------------------
echo create client X509 authentication certificate for admin user
set name=admin
:: create private key without passphrase
openssl genrsa -out %name%.key 2048

:: create certificate signing request
openssl req -new -sha256 -key %name%.key -config rootca.conf -out %name%.csr -subj "/C=US/ST=Missouri/L=Columbia/O=FairCom Corporation/OU=Security Department/CN=admin/emailAddress=support@faircom.com" -extensions client_ext

:: sign certificate with rootca key
openssl ca -md sha256 -days 3650 -in %name%.csr -out %name%.pem -keyfile private/rootca.key -config rootca.conf -cert rootca.pem -extensions client_ext

:: append the signing CA cert.
type rootca.pem >> %name%.pem

:: so now we have out user's .pem ... admin.pem
:: -----------------------------------------------------------------------------

:: -----------------------------------------------------------------------------
echo create client X509 authentication certificate for JonDoe user
set name=JonDoe
:: create private key without passphrase
openssl genrsa -out %name%.key 2048

:: create certificate signing request
openssl req -new -sha256 -key %name%.key -config rootca.conf -out %name%.csr -subj "/C=US/ST=Missouri/L=Columbia/O=FairCom Corporation/OU=Security Department/CN=Jon Doe/emailAddress=support@faircom.com" -extensions client_ext

:: sign certificate with rootca key
openssl ca -md sha256 -days 3650 -in %name%.csr -out %name%.pem -keyfile private/rootca.key -config rootca.conf -cert rootca.pem -extensions client_ext

:: append the signing CA cert.
type rootca.pem >> %name%.pem

:: so now we have out user's .pem ... JonDoe.pem
:: -----------------------------------------------------------------------------

exit/b
