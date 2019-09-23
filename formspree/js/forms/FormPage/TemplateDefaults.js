/** @format */

const subject = 'New submission from {{ _host }}'

const from_name = 'Formspree Team'

const style = `/**
 * /* -------------------------------------
 *     A very basic CSS reset
 * ------------------------------------- */

body {
  background-color: #fff;
  font-family: 'Open Sans', sans-serif;
  font-size: 16px;
  line-height: 1.45;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
}
table {
  width: 100%;
}
table td {
  vertical-align: top;
}
img {
  max-width: 100%;
}

/* -------------------------------------
    BODY & CONTAINER
------------------------------------- */

.body-wrap {
  background-color: #f9f9f8;
  margin: 0 auto;
}
.email-wrap {
  margin: 22px auto;
  max-width: 616px;
}
.content-wrap {
  padding: 22px;
}
.content-block {
  padding: 0 0 22px;
}

/* -------------------------------------
    HEADER, FOOTER, MAIN
------------------------------------- */

.header td {
  color: #103742;
  padding: 22px;
}
.email-title {
  font-family: 'Poppins', sans-serif;
  text-transform: uppercase;
  font-weight: 700;
  margin: 0;
}

.timestamp,
.timestamp a {
  color: #918f8d;
  font-size: 12px;
}

/* -------------------------------------
    TYPOGRAPHY
------------------------------------- */

h1,
h2,
h3 {
  font-family: 'Poppins', sans-serif;
  margin: 44px 0 0;
  font-weight: 400;
}
h1 {
  font-size: 32px;
  color: #0f0906;
  font-weight: 400;
}
h2 {
  font-size: 24px;
  color: #103742;
}
h3 {
  font-size: 18px;
  color: #666260;
}
h4 {
  font-size: 14px;
  font-weight: 700;
}
p,
ul,
ol {
  margin-bottom: 11px;
  font-weight: normal;
}
p li,
ul li,
ol li {
  margin-left: 5px;
  list-style-position: inside;
}
.form td {
  font-family: 'Source Code Pro', monospace;
}

/* -------------------------------------
    LINKS & BUTTONS
------------------------------------- */

a {
  color: #103742;
  text-decoration: underline;
}
.btn-primary {
  font-family: 'Poppins', sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.125em;
  text-transform: uppercase;
  text-decoration: none;
  text-align: center;
  white-space: nowrap;
  color: #f9f9f8;
  background-color: #103742;
  line-height: 2em;
  display: inline-block;
  padding: 0.707em 1.414em;
  cursor: pointer;
}

/* -------------------------------------
    OTHER STYLES THAT MIGHT BE USEFUL
------------------------------------- */

.last {
  margin-bottom: 0;
}
.first {
  margin-top: 0;
}
.aligncenter {
  text-align: center;
}
.alignright {
  text-align: right;
}
.alignleft {
  text-align: left;
}
.clear {
  clear: both;
}

.shadow {
  background-color: #cccccc;
}

.shadow .shadow-overlay {
  bottom: 4px;
  position: relative;
  right: 4px;
}

/* -------------------------------------
    Form
    Styles for the form data table
------------------------------------- */
.message {
  background-color: #fff;
}

.form {
  text-align: left;
}
.form td {
  padding: 11px;
}
.form .form-items td {
  font-size: 14px;
  border-bottom: #e3e3da 1px solid;
}
.form pre {
  margin: 4px 0; 
  font-family: inherit; 
  white-space: pre-wrap;
}
`

const body = `<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>New Form Submission</title>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1"/>
    <link href="https://fonts.googleapis.com/css?family=Poppins:400,700|Open+Sans:400,700|Source+Code+Pro" rel="stylesheet" data-premailer="ignore">
  </head>
  <body leftmargin="0" marginwidth="0" topmargin="0" marginheight="0" bgcolor="#ffffff" itemscope itemtype="http://schema.org/EmailMessage">

    <!-- body wrapper -->
    <table cellpadding="0" cellspacing="0" border="0" bgcolor="#f9f9f8" class="body-wrap">
      <tr>
        <td valign="top" align="center">

          <!-- email wrapper -->
          <table cellpadding="0" cellspacing="0" border="0" class="email-wrap">
            <tr>
              <td class="container">

                <!-- header -->
                <table cellpadding="0" cellspacing="0" border="0" class="header">
                  <tr>
                    <td align="center">
                      <p class="email-title">New Form Submission</p>
                    </td>
                  </tr>
                </table>
                <!-- /header -->
                
                <!-- main wrapper -->
                <table cellpadding="0" cellspacing="0" border="0" class="main content">
                  <tr>
                    <td class="content-wrap">

                      <!-- content wrapper -->
                      <table cellpadding="0" cellspacing="0" border="0">
                        <tr>
                          <td align="center" class="content-block">
                            Someone just submitted your form on {{ _host }}. <br><br> Here's what they had to say:
                          </td>
                        </tr>
                      </table>
                      <table cellpadding="0" cellspacing="0" border="0" class="message">
                        <tr>
                          <td align="center">
                            <table cellpadding="0" cellspacing="0" border="0" class="form">
                              <tr>
                                <td>
                                  <table cellpadding="0" cellspacing="0" border="0" class="form-items">
                                    {{# _fields }}
                                    <tr>
                                      <td>
                                        <strong>{{ _name }}:</strong><br>
                                        <pre>{{ _value }}</pre>
                                      </td>
                                    </tr>
                                  {{/ _fields }}
                                  </table>
                                </td>
                              </tr>
                              <tr>
                                <td align="center" class="content-block">
                                  <span class="timestamp">Submitted {{ _time }}.</span>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                      </table>
                      <!-- /content wrapper -->

                    </td>
                  </tr>
                </table>
                <!-- /main wrapper -->

                <!-- footer -->
                <table cellpadding="0" cellspacing="0" border="0" class="footer">
                  <tr>
                    <td align="center" class="aligncenter content-block">If you no longer wish to receive these emails, <a href="{{_unsubscribe}}">click here to unsubscribe</a>.<br>
                    </td>
                  </tr>
                </table>
                <!-- /footer -->
                                
              </td>
            </tr>
          </table>
          <!-- /email wrapper -->

        </td>
      </tr>
    </table>
    <!-- /body wrapper -->

  </body>
</html>`

export default {body, style, subject, from_name}
