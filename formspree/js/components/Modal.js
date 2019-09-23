/** @format */

const React = require('react')
const cs = require('class-set')

export default class Modal extends React.Component {
  constructor(props) {
    super(props)

    this.close = this.close.bind(this)
  }

  render() {
    let classes = this.props.className ? this.props.className.split() : []
    classes = cs(
      'modal',
      'react',
      this.props.isOpen ? 'target' : null,
      ...classes
    )
    return (
      <>
        <div
          className={cs({'modal-overlay': true, open: this.props.isOpen})}
          onClick={this.close}
        />
        <div className={classes}>
          <div className="container modal-container">
            {this.props.isOpen ? (
              <>
                <div className="header">
                  <div className="title">
                    {typeof this.props.title === 'string' ? (
                      <h4>{this.props.title}</h4>
                    ) : (
                      this.props.title
                    )}
                  </div>
                  <a href="#" className="x" onClick={this.close}>
                    &times;
                  </a>
                </div>
                {this.props.children}
              </>
            ) : null}
          </div>
        </div>
      </>
    )
  }

  close(e) {
    e.preventDefault()
    // e && e.preventDefault && e.preventDefault()
    this.props.closing && this.props.closing()
  }
}
